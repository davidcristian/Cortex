import asyncio
import os
import signal
import socket

import pytest
from fakeredis import FakeAsyncRedis, FakeServer
from grpc import aio
from redis.asyncio import Redis

from cortex_core import BuiltinTool, Clock, ScheduleStore, SessionStore, ToolCall, TurnStamp
from cortex_orchestrator import run_from_env, wiring
from cortex_orchestrator.config_schedule import ScheduleConfig
from cortex_orchestrator.schedule_builders import build_schedule_tools
from cortex_seam import BrainServiceStub, DeleteSessionRequest
from cortex_session import RedisScheduleStore, RedisSessionStore


def _free_loopback_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
    return port


async def _delete(address: str, session_id: str) -> None:
    async with aio.insecure_channel(address) as channel:
        await asyncio.wait_for(channel.channel_ready(), timeout=10)
        method = BrainServiceStub(channel).DeleteSession  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        await method(DeleteSessionRequest(session_id=session_id))


async def _add(tool: BuiltinTool, session_id: str, text: str) -> None:
    arguments = {"kind": "reminder", "text": text, "in_seconds": 3600}
    stamp = TurnStamp(session_id=session_id, tainted=False)
    result = await tool.invoke(
        ToolCall(id=text, name="schedule_task", arguments=arguments, stamp=stamp)
    )
    assert not result.is_error


async def test_the_brains_schedule_task_clears_a_chat_deleted_before_its_add(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port = _free_loopback_port()
    monkeypatch.setenv("CORTEX_SEAM_HOST", "127.0.0.1")
    monkeypatch.setenv("CORTEX_SEAM_PORT", str(port))
    monkeypatch.setenv("CORTEX_SCHEDULE_BACKEND", "redis")
    server = FakeServer()

    def fake_from_url(url: str) -> Redis:
        del url
        return FakeAsyncRedis(server=server)

    built: list[BuiltinTool] = []

    def recording(
        config: ScheduleConfig,
        schedules: ScheduleStore | None,
        clock: Clock,
        *,
        tasks_enabled: bool,
        sessions: SessionStore | None = None,
    ) -> list[BuiltinTool]:
        made = build_schedule_tools(
            config, schedules, clock, tasks_enabled=tasks_enabled, sessions=sessions
        )
        built.extend(made)
        return made

    monkeypatch.setattr(Redis, "from_url", fake_from_url)
    monkeypatch.setattr(wiring, "build_schedule_tools", recording)
    chats = RedisSessionStore(FakeAsyncRedis(server=server))
    task = asyncio.create_task(run_from_env(store_factory=lambda _url: chats))
    reader = RedisScheduleStore(FakeAsyncRedis(server=server))
    try:
        await _delete(f"127.0.0.1:{port}", "gone")
        (schedule_task,) = [tool for tool in built if tool.spec.name == "schedule_task"]
        await _add(schedule_task, "gone", "in the deleted chat")
        await _add(schedule_task, "live", "in the live chat")
        origins = {item.text: item.session_id for item in await reader.list_active()}
        os.kill(os.getpid(), signal.SIGTERM)
        await asyncio.wait_for(task, timeout=10)
    finally:
        task.cancel()
        await reader.aclose()
    assert origins == {"in the deleted chat": "", "in the live chat": "live"}
