"""run_from_env composes env config + Redis store + echo backend and serves the seam."""

import asyncio
import logging
import os
import signal
import socket
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import cast

import pytest
from fakeredis import FakeAsyncRedis, FakeServer
from grpc import aio

from cortex_core import (
    EchoInferenceBackend,
    InMemoryTaskStore,
    InMemoryToolRegistry,
    MemoryRecaller,
    PlacementRequest,
    PlacementTarget,
    ResourceBudgetScheduler,
    SpawnSubagentsTool,
    SubagentResources,
    SubagentRunner,
    SystemClock,
    ToolCall,
    ToolDispatcher,
    ToolError,
    ToolNotFoundError,
    ToolSpec,
    VramBudgetPlacer,
)
from cortex_inference import LlamaCppBackend
from cortex_memory import PgVectorMemoryStore
from cortex_orchestrator import (
    InferenceConfig,
    MemoryConfig,
    SubagentsConfig,
    ToolsConfig,
    build_cortex_tools,
    build_inference_backend,
    build_memory,
    build_subagents,
    build_tool_registry,
    run_from_env,
)
from cortex_seam import BrainServiceStub, ClientEvent, ServerEvent, UserTurn
from cortex_session import RedisSessionStore, RedisTaskStore
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


async def test_build_tool_registry_defaults_to_disabled() -> None:
    """The MCP-less default: no registry, and a closer that is a clean no-op."""
    registry, close = await build_tool_registry(ToolsConfig(backend="none"))
    assert registry is None
    await close()  # no resources to release; must not raise


async def test_build_tool_registry_selects_mcp_and_returns_a_closer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The opt-in path: the raw MCP registry (shared by cortex + subagents) + a closer."""
    closed: list[str] = []
    seen_url: list[str] = []

    async def fake_connect(url: str) -> tuple[object, Callable[[], Awaitable[None]]]:
        seen_url.append(url)

        async def closer() -> None:
            closed.append("session")

        return object(), closer

    monkeypatch.setattr(McpToolRegistry, "connect", fake_connect)
    registry, close = await build_tool_registry(
        ToolsConfig(backend="mcp", endpoint="http://fs:9000/mcp")
    )
    assert registry is not None
    assert seen_url == ["http://fs:9000/mcp"]
    await close()  # releases the MCP session
    assert closed == ["session"]


def _canned_registry(url: str, *names: str) -> InMemoryToolRegistry:
    """One tool per name, each replying with the URL it came from, so routing is visible."""

    async def reply(arguments: Mapping[str, object]) -> str:
        del arguments
        return url

    return InMemoryToolRegistry(
        {n: (ToolSpec(name=n, description="", parameters={}), reply) for n in names}
    )


async def test_build_tool_registry_filters_and_aggregates_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Several endpoints: per-endpoint allowlists apply, and one aggregate spans them all
    in sorted-name order (ADR-0009 refinements addendum)."""
    fs_url = "http://mcp-filesystem:9000/mcp"
    mail_url = "http://mcp-email:9100/mcp"
    canned = {
        fs_url: _canned_registry(fs_url, "read_text_file", "write_file"),
        mail_url: _canned_registry(mail_url, "read_email"),
    }
    closed: list[str] = []

    async def fake_connect(url: str) -> tuple[object, Callable[[], Awaitable[None]]]:
        async def closer() -> None:
            closed.append(url)

        return canned[url], closer

    monkeypatch.setattr(McpToolRegistry, "connect", fake_connect)
    registry, close = await build_tool_registry(
        ToolsConfig(
            backend="mcp",
            endpoints={"filesystem": fs_url, "email": mail_url},
            allow={"filesystem": ("read_text_file",)},
        )
    )
    assert registry is not None
    # "email" sorts before "filesystem"; the filesystem write tool is filtered out.
    names = [spec.name for spec in await registry.describe_tools()]
    assert names == ["read_email", "read_text_file"]
    routed = await registry.invoke(ToolCall(id="c1", name="read_text_file", arguments={}))
    assert routed.content == fs_url
    with pytest.raises(ToolNotFoundError, match="unknown tool 'write_file'"):
        await registry.invoke(ToolCall(id="c2", name="write_file", arguments={}))
    await close()  # releases every session, LIFO
    assert closed == [fs_url, mail_url]


class DeadListingRegistry:
    """A connected registry whose listing fails (the sidecar died after connect)."""

    async def describe_tools(self) -> Sequence[ToolSpec]:
        msg = "sidecar gone"
        raise ToolError(msg)

    async def invoke(self, call: ToolCall) -> object:
        del call
        msg = "never routed to"
        raise ToolError(msg)


async def test_build_tool_registry_skip_mode_serves_around_a_dead_sidecar(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """CORTEX_TOOLS_ON_UNAVAILABLE=skip: healthy sidecars serve, the dead one is logged."""
    fs_url = "http://mcp-filesystem:9000/mcp"
    mail_url = "http://mcp-email:9100/mcp"
    canned: dict[str, object] = {
        fs_url: _canned_registry(fs_url, "read_text_file"),
        mail_url: DeadListingRegistry(),
    }

    async def fake_connect(url: str) -> tuple[object, Callable[[], Awaitable[None]]]:
        async def closer() -> None:
            return

        return canned[url], closer

    monkeypatch.setattr(McpToolRegistry, "connect", fake_connect)
    registry, close = await build_tool_registry(
        ToolsConfig(
            backend="mcp",
            endpoints={"filesystem": fs_url, "email": mail_url},
            on_unavailable="skip",
        )
    )
    assert registry is not None
    with caplog.at_level(logging.WARNING, logger="cortex_orchestrator.wiring"):
        names = [spec.name for spec in await registry.describe_tools()]
    assert names == ["read_text_file"]  # the email sidecar is skipped, not fatal
    (record,) = caplog.records  # … and reported, never silent
    # The reporter's structured fields ride on the LogRecord as dynamic attributes.
    assert getattr(record, "sidecar", "") == "email"
    assert "sidecar gone" in str(getattr(record, "error", ""))
    await close()


async def test_build_tool_registry_unwinds_sessions_when_a_later_connect_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed connect must not leak the sessions already opened before it."""
    closed: list[str] = []

    async def fake_connect(url: str) -> tuple[object, Callable[[], Awaitable[None]]]:
        if url == "http://b:9100/mcp":
            msg = "connect refused"
            raise ToolError(msg)

        async def closer() -> None:
            closed.append(url)

        return _canned_registry(url, "read"), closer

    monkeypatch.setattr(McpToolRegistry, "connect", fake_connect)
    config = ToolsConfig(
        backend="mcp",
        endpoints={"a": "http://a:9000/mcp", "b": "http://b:9100/mcp"},
    )
    with pytest.raises(ToolError, match="connect refused"):
        await build_tool_registry(config)
    assert closed == ["http://a:9000/mcp"]


async def test_build_subagents_defaults_to_disabled() -> None:
    """The default: no spawn tool, and a closer that is a clean no-op."""
    spawn, close = await build_subagents(
        SubagentsConfig(backend="none"),
        None,
        "redis://x:6379/0",
        SystemClock(),
        placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.3),
    )
    assert spawn is None
    await close()  # no resources to release; must not raise


# None and an empty MCP registry both exercised: the subagent-tools branch runs either way.
@pytest.mark.parametrize("registry", [None, InMemoryToolRegistry({})])
async def test_build_subagents_selects_llamacpp_and_returns_a_closer(
    registry: InMemoryToolRegistry | None,
) -> None:
    """The opt-in path: a spawn tool over a CPU backend + Redis task store, plus a closer."""
    seen_url: list[str] = []

    def factory(url: str) -> RedisTaskStore:
        seen_url.append(url)
        return RedisTaskStore(FakeAsyncRedis(server=FakeServer()))

    config = SubagentsConfig(
        backend="llamacpp",
        endpoint="http://llama-subagent-cpu:8082",
        gpu_endpoint="http://llama-subagent-gpu:8083",
    )
    spawn, close = await build_subagents(
        config,
        registry,
        "redis://sub:6379/0",
        SystemClock(),
        placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.3),
        task_store_factory=factory,
    )
    assert isinstance(spawn, SpawnSubagentsTool)
    assert seen_url == ["redis://sub:6379/0"]
    await close()  # releases the fake task store + the httpx client


async def _read_handler(arguments: Mapping[str, object]) -> str:
    del arguments
    return "ok"


def _spawn_tool() -> SpawnSubagentsTool:
    store = InMemoryTaskStore()
    echo = EchoInferenceBackend()
    resources = SubagentResources(
        backends={PlacementTarget.GPU: echo, PlacementTarget.CPU: echo},
        scheduler=ResourceBudgetScheduler(4.0, 8.0),
        placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.3),
        request=PlacementRequest("s", vram_gb=2.0, cpus=2.0, memory_gb=2.0),
    )
    return SpawnSubagentsTool(SubagentRunner(store, resources, SystemClock()), store, SystemClock())


def _read_registry() -> InMemoryToolRegistry:
    return InMemoryToolRegistry(
        {"read": (ToolSpec(name="read", description="", parameters={}), _read_handler)}
    )


def test_build_cortex_tools_none_when_nothing_is_enabled() -> None:
    assert build_cortex_tools(None, None, SystemClock()) is None


async def test_build_cortex_tools_merges_the_spawn_tool_with_mcp_tools() -> None:
    tools = build_cortex_tools(_read_registry(), _spawn_tool(), SystemClock())
    assert isinstance(tools, ToolDispatcher)
    assert {spec.name for spec in await tools.describe_tools()} == {"spawn_subagents", "read"}


async def test_build_cortex_tools_spawn_only_when_no_mcp() -> None:
    tools = build_cortex_tools(None, _spawn_tool(), SystemClock())
    assert isinstance(tools, ToolDispatcher)
    assert {spec.name for spec in await tools.describe_tools()} == {"spawn_subagents"}


async def test_build_cortex_tools_mcp_only_when_no_subagents() -> None:
    tools = build_cortex_tools(_read_registry(), None, SystemClock())
    assert isinstance(tools, ToolDispatcher)
    assert {spec.name for spec in await tools.describe_tools()} == {"read"}
