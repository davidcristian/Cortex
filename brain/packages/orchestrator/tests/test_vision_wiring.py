"""The composition root's vision decisions, driven through ``run_from_env`` itself (ADR-0029)."""

import asyncio
import os
import signal
import socket
from collections.abc import Awaitable, Callable, Sequence
from typing import cast

import pytest
from fakeredis import FakeAsyncRedis, FakeServer
from grpc import aio
from redis.asyncio import Redis

from cortex_body_client import GrpcBodyGateway
from cortex_core import (
    CAPTURE_SCREEN_TOOL_NAME,
    GET_VOLUME_TOOL_NAME,
    BodyGateway,
    BrainPhase,
    BuiltinTool,
    CaptureAsk,
    InMemoryBodyGateway,
    ScriptedVisionProbe,
    ToolCall,
    ToolDispatcher,
    TurnCapabilities,
)
from cortex_orchestrator import build_builtin_tools, engines, run_from_env, wiring
from cortex_orchestrator.builders import build_cortex_tools
from cortex_orchestrator.config import InferenceConfig
from cortex_orchestrator.config_body import BodyConfig
from cortex_orchestrator.vision import build_vision
from cortex_seam import BrainServiceStub, ClientEvent, ServerEvent, UserTurn
from cortex_session import RedisSessionStore


def _free_loopback_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
    return port


class _Root:
    """What one ``run_from_env`` composition decided, recorded from inside the root."""

    def __init__(self) -> None:
        self.builtin_sets: list[list[BuiltinTool]] = []
        self.builds: list[tuple[str, str]] = []
        self.dispatchers: list[ToolDispatcher] = []
        self.deep_capabilities: list[TurnCapabilities] = []
        self.scripted: ScriptedVisionProbe | None = None
        self.body = InMemoryBodyGateway()

    def names(self, which: int) -> list[str]:
        return [tool.spec.name for tool in self.builtin_sets[which]]

    async def offered(self) -> set[str]:
        """What the cortex's own dispatcher advertises, which is what the model is offered."""
        return {spec.name for spec in await self.dispatchers[0].describe_tools()}

    async def deep_tools(self) -> set[str]:
        (deep,) = self.deep_capabilities
        assert deep.tools is not None
        return {spec.name for spec in await deep.tools.describe_tools()}

    async def captures(self) -> Sequence[CaptureAsk]:
        return self.body.captures


def _record(monkeypatch: pytest.MonkeyPatch, root: _Root, vision_answers: tuple[bool, ...]) -> None:
    """Wrap the four root collaborators whose arguments and products this suite reads back."""
    real_builtins = build_builtin_tools
    real_vision = build_vision
    real_tools = build_cortex_tools
    real_phase = BrainPhase

    def recording_builtins(*args: object, **kwargs: object) -> list[BuiltinTool]:
        built = real_builtins(*args, **kwargs)  # pyright: ignore[reportCallIssue, reportArgumentType]
        root.builtin_sets.append(built)
        return built

    def recording_vision(
        config: InferenceConfig, body_config: BodyConfig, body: object
    ) -> tuple[object, object, Callable[[], Awaitable[None]]]:
        root.builds.append((config.vision, config.endpoint))
        bounds, probe, close = real_vision(config, body_config, cast("BodyGateway | None", body))
        if vision_answers and probe is not None:
            root.scripted = ScriptedVisionProbe(vision_answers)
            probe = root.scripted
        return bounds, probe, close

    def recording_tools(*args: object, **kwargs: object) -> ToolDispatcher | None:
        built = real_tools(*args, **kwargs)  # pyright: ignore[reportCallIssue, reportArgumentType]
        if built is not None:
            root.dispatchers.append(built)
        return built

    def recording_phase(*args: object) -> object:
        # The capabilities bundle by position, not from the end: the spill watch's declared floor
        # now rides after it (ADR-0030 spill-watch addendum).
        root.deep_capabilities.append(cast("TurnCapabilities", args[4]))
        return real_phase(*args)  # pyright: ignore[reportCallIssue, reportArgumentType]

    # Two of the four are patched where the per-stream factory reads them (`engines.py`): the
    # root assembles the two built-in sets and probes for vision, and the factory is what turns
    # a set into a dispatcher and hands the deep tier's bundle to its phase.
    monkeypatch.setattr(wiring, "build_builtin_tools", recording_builtins)
    monkeypatch.setattr(wiring, "build_vision", recording_vision)
    monkeypatch.setattr(engines, "build_cortex_tools", recording_tools)
    monkeypatch.setattr(engines, "BrainPhase", recording_phase)


async def _compose(
    monkeypatch: pytest.MonkeyPatch,
    *,
    env: dict[str, str],
    vision_answers: tuple[bool, ...] = (),
) -> _Root:
    """Run the real composition root against a fake body, one turn, then shut it down."""
    root = _Root()
    port = _free_loopback_port()
    monkeypatch.setenv("CORTEX_SEAM_HOST", "127.0.0.1")
    monkeypatch.setenv("CORTEX_SEAM_PORT", str(port))
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    server = FakeServer()

    def fake_from_url(url: str) -> Redis:
        del url
        return FakeAsyncRedis(server=server)

    monkeypatch.setattr(Redis, "from_url", fake_from_url)

    async def fake_connect(
        endpoint: str,
        *,
        token: str = "",
        capture_timeout_s: float = 10.0,
        call_timeout_s: float = 5.0,
    ) -> tuple[object, Callable[[], Awaitable[None]]]:
        del endpoint, token, capture_timeout_s, call_timeout_s

        async def closer() -> None:
            return None

        return root.body, closer

    monkeypatch.setattr(GrpcBodyGateway, "connect", fake_connect)

    _record(monkeypatch, root, vision_answers)

    task = asyncio.create_task(
        run_from_env(store_factory=lambda _url: RedisSessionStore(FakeAsyncRedis(server=server)))
    )
    try:
        async with aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            await asyncio.wait_for(channel.channel_ready(), timeout=10)
            stub = BrainServiceStub(channel)
            converse = stub.Converse  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            call = cast("aio.StreamStreamCall[ClientEvent, ServerEvent]", converse())
            await call.write(ClientEvent(session_id="vision", user_turn=UserTurn(text="hi")))
            await call.done_writing()
            assert [event async for event in call], "the turn produced no events at all"
        os.kill(os.getpid(), signal.SIGTERM)
        await asyncio.wait_for(task, timeout=10)
    finally:
        task.cancel()
    return root


_BODY = {"CORTEX_BODY_BACKEND": "grpc", "CORTEX_BODY_ENDPOINT": "host.docker.internal:50151"}
_ESCALATION = {
    "CORTEX_ESCALATION": "1",
    "CORTEX_MODELHOST_BACKEND": "scripted",
    "CORTEX_BRAIN_ENDPOINT": "http://llama-brain:8081",
}


async def test_the_probes_answer_decides_whether_the_screen_is_offered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Discovered, not declared: the same env, the same body, and only the probe's verdict differs.
    """
    seeing = await _compose(
        monkeypatch,
        env={**_BODY, "CORTEX_VISION": "auto", "CORTEX_INFERENCE_ENDPOINT": "http://cortex:8080"},
        vision_answers=(True,),
    )
    assert seeing.builds == [("auto", "http://cortex:8080")]
    assert CAPTURE_SCREEN_TOOL_NAME in await seeing.offered()

    blind = await _compose(
        monkeypatch,
        env={**_BODY, "CORTEX_VISION": "auto", "CORTEX_INFERENCE_ENDPOINT": "http://cortex:8080"},
        vision_answers=(False,),
    )
    assert blind.builds == [("auto", "http://cortex:8080")]
    offered = await blind.offered()
    assert CAPTURE_SCREEN_TOOL_NAME not in offered
    assert GET_VOLUME_TOOL_NAME in offered, "the body's other tools are unaffected"


async def test_a_capture_the_model_can_no_longer_read_reads_no_pixels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reproduced failure, refused at the root: advertised honestly, then the server changed."""
    root = await _compose(
        monkeypatch,
        env={**_BODY, "CORTEX_VISION": "auto", "CORTEX_INFERENCE_ENDPOINT": "http://cortex:8080"},
        vision_answers=(True,),
    )
    assert CAPTURE_SCREEN_TOOL_NAME in await root.offered(), "honest when it was advertised"
    assert root.scripted is not None
    # The model host is recreated without its projector, under a brain that never restarts.
    root.scripted.rescript([False])

    result = await root.dispatchers[0].dispatch(
        ToolCall(id="c1", name=CAPTURE_SCREEN_TOOL_NAME, arguments={"target": "display"})
    )

    assert result.is_error is True
    assert "the screen was not read" in result.content
    assert await root.captures() == (), "the body was never asked for a picture"


async def test_the_owners_off_switch_needs_no_server_to_be_believed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``off`` is resolved by the real ``build_vision``, so no tool lands and nothing is probed."""
    root = await _compose(monkeypatch, env={**_BODY, "CORTEX_VISION": "off"})
    assert root.builds == [("off", "")]
    assert CAPTURE_SCREEN_TOOL_NAME not in root.names(0)
    assert CAPTURE_SCREEN_TOOL_NAME not in await root.offered()


async def test_without_a_body_nothing_is_built_to_probe_with(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No body, no capture, so there is no reason to ask a model server anything."""
    root = await _compose(monkeypatch, env={"CORTEX_VISION": "on"})
    assert root.builds == [("on", "")]
    assert CAPTURE_SCREEN_TOOL_NAME not in root.names(0)


async def test_the_capture_bounds_the_tool_asks_for_come_from_body_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The knobs, asserted at the far end: what the body was actually asked for."""
    root = await _compose(
        monkeypatch,
        env={
            **_BODY,
            "CORTEX_VISION": "on",
            "CORTEX_BODY_CAPTURE_MAX_EDGE": "1280",
            "CORTEX_BODY_MAX_IMAGE_BYTES": "4000000",
        },
    )
    capture = next(
        tool for tool in root.builtin_sets[0] if tool.spec.name == CAPTURE_SCREEN_TOOL_NAME
    )
    await capture.invoke(
        ToolCall(id="c1", name=CAPTURE_SCREEN_TOOL_NAME, arguments={"target": "display"})
    )
    assert [(ask.max_edge, ask.max_bytes) for ask in await root.captures()] == [(1280, 4_000_000)]


async def test_the_deep_tier_is_never_offered_the_screen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The tier that swaps in is text-only by construction, so it must not be offered eyes."""
    root = await _compose(
        monkeypatch,
        env={**_BODY, **_ESCALATION, "CORTEX_VISION": "on"},
    )
    assert CAPTURE_SCREEN_TOOL_NAME in root.names(0), "the cortex keeps its eyes"
    deep = await root.deep_tools()
    assert CAPTURE_SCREEN_TOOL_NAME not in deep
    assert GET_VOLUME_TOOL_NAME in deep, "the deep tier keeps every other built-in"
