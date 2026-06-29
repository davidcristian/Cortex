"""run_from_env composes env config + Redis store + echo backend and serves the seam."""

import asyncio
import os
import signal
import socket
from collections.abc import Awaitable, Callable, Sequence
from typing import cast

import pytest
from fakeredis import FakeAsyncRedis, FakeServer
from grpc import aio

from cortex_core import EchoInferenceBackend, MemoryRecaller, SystemClock, ToolDispatcher
from cortex_inference import LlamaCppBackend
from cortex_memory import PgVectorMemoryStore
from cortex_orchestrator import (
    InferenceConfig,
    MemoryConfig,
    ToolsConfig,
    build_inference_backend,
    build_memory,
    build_tools,
    run_from_env,
)
from cortex_seam import BrainServiceStub, ClientEvent, ServerEvent, UserTurn
from cortex_session import RedisSessionStore
from cortex_tools import McpToolRegistry


def _free_loopback_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
    return port


class RecordingStore(RedisSessionStore):
    """A fakeredis-backed store that records whether the runtime closed it."""

    def __init__(self) -> None:
        super().__init__(FakeAsyncRedis(server=FakeServer()))
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True
        await super().aclose()


async def _run_one_turn(address: str, session_id: str, text: str) -> list[ServerEvent]:
    async with aio.insecure_channel(address) as channel:
        await asyncio.wait_for(channel.channel_ready(), timeout=10)
        stub = BrainServiceStub(channel)
        converse = stub.Converse  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        call = cast("aio.StreamStreamCall[ClientEvent, ServerEvent]", converse())
        await call.write(ClientEvent(session_id=session_id, user_turn=UserTurn(text=text)))
        await call.done_writing()
        return [event async for event in call]


def _reply_text(events: Sequence[ServerEvent]) -> str:
    return "".join(e.text_delta.text for e in events if e.WhichOneof("event") == "text_delta")


async def test_run_from_env_serves_turns_and_closes_the_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port = _free_loopback_port()
    monkeypatch.setenv("CORTEX_SEAM_HOST", "127.0.0.1")
    monkeypatch.setenv("CORTEX_SEAM_PORT", str(port))
    monkeypatch.setenv("CORTEX_REDIS_URL", "redis://redis.test.invalid:6379/5")
    store = RecordingStore()
    seen_urls: list[str] = []

    def factory(url: str) -> RedisSessionStore:
        seen_urls.append(url)
        return store

    task = asyncio.create_task(run_from_env(store_factory=factory))
    try:
        events = await _run_one_turn(f"127.0.0.1:{port}", "wired", "hello")
        assert _reply_text(events) == "reply 1: hello"
        os.kill(os.getpid(), signal.SIGTERM)
        await asyncio.wait_for(task, timeout=10)
    finally:
        task.cancel()
    # The factory got the env URL; the turn went through the injected store; and the
    # composition root released the store's connections on the way out.
    assert seen_urls == ["redis://redis.test.invalid:6379/5"]
    assert [m.text for m in await store.history("wired")] == ["hello", "reply 1: hello"]
    assert store.closed is True


async def test_run_from_env_default_store_surfaces_redis_outage_as_seam_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With the real default factory and no Redis, a turn fails as a SeamError event."""
    port = _free_loopback_port()
    monkeypatch.setenv("CORTEX_SEAM_HOST", "127.0.0.1")
    monkeypatch.setenv("CORTEX_SEAM_PORT", str(port))
    # TEST-NET port 1 on loopback: connection refused immediately, no retry loop.
    monkeypatch.setenv("CORTEX_REDIS_URL", "redis://127.0.0.1:1/0")
    task = asyncio.create_task(run_from_env())
    try:
        events = await _run_one_turn(f"127.0.0.1:{port}", "s", "hello")
        os.kill(os.getpid(), signal.SIGTERM)
        await asyncio.wait_for(task, timeout=10)
    finally:
        task.cancel()
    (only,) = events
    assert only.WhichOneof("event") == "error"
    assert only.error.code == "session_store_unavailable"


async def test_build_inference_backend_defaults_to_echo() -> None:
    """The GPU-less default: Echo, with a closer that is a clean no-op."""
    backend, close = build_inference_backend(InferenceConfig(backend="echo", endpoint=""), "cortex")
    assert isinstance(backend, EchoInferenceBackend)
    await close()  # no resources to release; must not raise


async def test_build_inference_backend_selects_llamacpp_and_returns_a_closer() -> None:
    """The opt-in GPU path: the real adapter, with the HTTP client's aclose as the closer."""
    config = InferenceConfig(backend="llamacpp", endpoint="http://llama-cortex:8080")
    backend, close = build_inference_backend(config, "cortex")
    assert isinstance(backend, LlamaCppBackend)
    await close()  # releases the httpx client


async def test_build_memory_defaults_to_disabled() -> None:
    """The DB-less default: no recaller, and a closer that is a clean no-op."""
    memory, close = await build_memory(MemoryConfig(backend="none"), SystemClock())
    assert memory is None
    await close()  # no resources to release; must not raise


async def test_build_memory_selects_pgvector_and_returns_a_closer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The opt-in path: a recaller over the pgvector store, whose closer releases the pool."""
    closed: list[str] = []
    seen_dsn: list[str] = []

    class FakeStore:
        async def aclose(self) -> None:
            closed.append("store")

    async def fake_connect(dsn: str) -> FakeStore:
        seen_dsn.append(dsn)
        return FakeStore()

    monkeypatch.setattr(PgVectorMemoryStore, "connect", fake_connect)
    config = MemoryConfig(
        backend="pgvector",
        dsn="postgresql://cortex@db/cortex",
        embedder_endpoint="http://llama-embed:8081",
    )
    memory, close = await build_memory(config, SystemClock())
    assert isinstance(memory, MemoryRecaller)
    assert seen_dsn == ["postgresql://cortex@db/cortex"]
    await close()  # releases the pool and the embedder client
    assert closed == ["store"]


async def test_build_tools_defaults_to_disabled() -> None:
    """The MCP-less default: no dispatcher, and a closer that is a clean no-op."""
    tools, close = await build_tools(ToolsConfig(backend="none"), SystemClock())
    assert tools is None
    await close()  # no resources to release; must not raise


async def test_build_tools_selects_mcp_and_returns_a_closer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The opt-in path: an audited dispatcher over the MCP registry, whose closer releases it."""
    closed: list[str] = []
    seen_url: list[str] = []

    async def fake_connect(url: str) -> tuple[object, Callable[[], Awaitable[None]]]:
        seen_url.append(url)

        async def closer() -> None:
            closed.append("session")

        return object(), closer

    monkeypatch.setattr(McpToolRegistry, "connect", fake_connect)
    config = ToolsConfig(backend="mcp", endpoint="http://fs:9000/mcp")
    tools, close = await build_tools(config, SystemClock())
    assert isinstance(tools, ToolDispatcher)
    assert seen_url == ["http://fs:9000/mcp"]
    await close()  # releases the MCP session
    assert closed == ["session"]
