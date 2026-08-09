"""run_from_env composes env config + Redis store + echo backend and serves the seam."""

import asyncio
import logging
import os
import signal
import socket
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import cast

import httpx
import pytest
from fakeredis import FakeAsyncRedis, FakeServer
from grpc import aio
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool
from redis.asyncio import Redis

import cortex_orchestrator.builders as builders_module
import cortex_orchestrator.subagent_builders as subagent_builders_module
from cortex_body_client import GrpcBodyGateway
from cortex_core import (
    CAPTURE_SCREEN_TOOL_NAME,
    DENIED_MSG,
    GET_VOLUME_TOOL_NAME,
    RAW_RECALL_POLICY,
    SET_VOLUME_TOOL_NAME,
    USER_DECLINED_MSG,
    CaptureBounds,
    CharBudgetHistoryWindow,
    DispatchPolicy,
    EchoInferenceBackend,
    GenerationBounds,
    GlobalMemoryScope,
    InferenceError,
    InferenceEvent,
    InMemoryBodyGateway,
    InMemorySessionStore,
    InMemoryTaskStore,
    InMemoryToolRegistry,
    JsonSchema,
    JudgeRecallPolicy,
    MemoryRecaller,
    Message,
    MmrRecallPolicy,
    PlacementRequest,
    PlacementTarget,
    RecallPolicy,
    RecencyMmrRecallPolicy,
    RecordingConfirmer,
    RerankingRecallPolicy,
    ResourceBudgetScheduler,
    Role,
    ScheduledItem,
    ScheduleKind,
    SessionMemoryCascade,
    SessionMemoryScope,
    SpawnSubagentsTool,
    StrictUrlRedactingGuardrail,
    SubagentProfile,
    SubagentResources,
    SubagentRoster,
    SubagentRunner,
    SystemClock,
    ToolCall,
    ToolDispatcher,
    ToolNotFoundError,
    ToolSpec,
    TurnStamp,
    UrlRedactingGuardrail,
    VramBudgetPlacer,
)
from cortex_core.summarizing import SummarizingHistoryWindow
from cortex_core.windowing import HistoryWindow
from cortex_inference import LlamaCppBackend
from cortex_memory import LoggingRecallSink, PgVectorMemoryStore
from cortex_orchestrator import (
    BodyConfig,
    BrainRuntimeConfig,
    InferenceConfig,
    MemoryConfig,
    SubagentRosterEntry,
    SubagentsConfig,
    ToolsConfig,
    build_body_gateway,
    build_builtin_tools,
    build_cortex_tools,
    build_inference_backend,
    build_memory,
    build_output_guardrail,
    build_subagent_tools,
    build_subagents,
    build_tool_registry,
    memory_scope_from_name,
    recall_audit_from_config,
    recall_policy_from_config,
    run_from_env,
)
from cortex_orchestrator.window_builders import build_history_window
from cortex_seam import (
    BrainServiceStub,
    ClientEvent,
    ListDueRemindersReply,
    ListDueRemindersRequest,
    ServerEvent,
    UserTurn,
)
from cortex_session import RedisScheduleStore, RedisSessionStore, RedisTaskStore


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


async def test_the_generation_client_bounds_every_phase_including_the_read() -> None:
    """The founding client passed ``read=None``, which is the wait nothing else bounded.

    Whole-value equality against literals, so the read ceiling is pinned along with the other
    three phases and ``None`` cannot satisfy it: a client that reads without a deadline holds
    its model lease, and a subagent's admission, for as long as a wedged server stays quiet.
    """
    client = builders_module.build_generation_client(45.5)
    try:
        assert client.timeout == httpx.Timeout(connect=10.0, read=45.5, write=10.0, pool=10.0)
    finally:
        await client.aclose()


@asynccontextmanager
async def _wedged_llama_server() -> AsyncGenerator[str]:
    """A loopback server that answers with the SSE headers and then never sends a chunk.

    The wedge the ceiling exists for. `httpx.MockTransport` cannot stand in: a timeout is
    enforced by the network stream underneath the transport, so a faked one would prove the
    plumbing and never the bound.
    """
    stop = asyncio.Event()

    async def serve_wedged(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await reader.readline()  # the request line; the small body needs no draining
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n\r\n")
        await writer.drain()
        await stop.wait()  # hold it open, sending nothing, until the test tears the server down
        writer.close()

    server = await asyncio.start_server(serve_wedged, "127.0.0.1", 0)
    port = cast("int", server.sockets[0].getsockname()[1])
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        stop.set()
        server.close()
        await server.wait_closed()


async def test_a_wedged_llama_server_fails_the_stream_instead_of_waiting_forever() -> None:
    """End to end over a real socket: the configured ceiling reaches the wire and fires there.

    The whole chain in one assertion, because each link is uninteresting alone: the config's
    seconds reach the client, the client applies them to the read, and the adapter translates
    what comes back into the port's own error. Bounded by `asyncio.timeout`, so restoring
    ``read=None`` (or hard-coding a ceiling in place of the config's) reddens this in ten
    seconds rather than hanging the suite, which proves nothing.
    """
    async with _wedged_llama_server() as endpoint:
        config = InferenceConfig(backend="llamacpp", endpoint=endpoint, stall_timeout_s=0.25)
        backend, close = build_inference_backend(config, "cortex")
        try:
            turn = Message(role=Role.USER, text="hello", at=datetime.now(UTC), turn_id="t-1")
            async with asyncio.timeout(10.0):
                with pytest.raises(InferenceError, match="sent nothing for model 'cortex'"):
                    async for _event in backend.stream("cortex", [turn]):
                        pass  # a wedged server streams nothing, so this body never runs
        finally:
            await close()


async def test_build_memory_defaults_to_disabled() -> None:
    """The DB-less default: no recaller, no cascade, and a closer that is a clean no-op."""
    memory, cascade, close = await build_memory(
        MemoryConfig(backend="none"), SystemClock(), EchoInferenceBackend(), "cortex"
    )
    assert memory is None
    assert cascade is None  # nothing to forget with no backend, so DeleteSession skips the cascade
    await close()  # no resources to release; must not raise


async def test_build_memory_selects_pgvector_and_returns_a_closer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The opt-in path: a recaller and a delete cascade over the pgvector store, closer frees it."""
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
    memory, cascade, close = await build_memory(
        config, SystemClock(), EchoInferenceBackend(), "cortex"
    )
    assert isinstance(memory, MemoryRecaller)
    assert isinstance(cascade, SessionMemoryCascade)  # DeleteSession's out-of-band forget path
    assert seen_dsn == ["postgresql://cortex@db/cortex"]
    await close()  # releases the pool and the embedder client
    assert closed == ["store"]


def test_recall_audit_from_config_is_opt_in() -> None:
    """The recall trail is off by default (ADR-0038): a silent path, not a sink that drops."""
    assert recall_audit_from_config(MemoryConfig()) is None
    audited = recall_audit_from_config(MemoryConfig(recall_audit=True))
    assert isinstance(audited, LoggingRecallSink)


def test_memory_scope_from_name_maps_config_to_the_policy() -> None:
    """The one env→core seam for scoping: `global` (default) vs `session` (ADR-0008 addendum)."""
    assert isinstance(memory_scope_from_name("global"), GlobalMemoryScope)
    assert isinstance(memory_scope_from_name("session"), SessionMemoryScope)


def _policy(config: MemoryConfig) -> RecallPolicy:
    """`recall_policy_from_config` with the two model-rank arguments fixed (ADR-0038)."""
    return recall_policy_from_config(config, EchoInferenceBackend(), "cortex")


def test_recall_policy_from_config_maps_config_to_the_policy() -> None:
    """The one env→core seam for reranking: `judge` (default), `raw`, `reranked`, `mmr`."""
    # The shipped default is the model rank (ADR-0038 turn-cost addendum), and `raw` is what a
    # deployment sets to get the founding top-k cosine back, so both directions are pinned here.
    assert isinstance(_policy(MemoryConfig()), JudgeRecallPolicy)
    assert _policy(MemoryConfig(recall="raw")) is RAW_RECALL_POLICY
    reranked = _policy(MemoryConfig(recall="reranked"))
    assert isinstance(reranked, RerankingRecallPolicy)
    # The half-life knob is authored in days and reaches the policy converted to seconds.
    assert (
        _policy(MemoryConfig(recall="reranked", recall_half_life_days=1.0)).candidate_k(5)
        == 5 * MemoryConfig().recall_pool_factor
    )
    mmr = _policy(MemoryConfig(recall="mmr"))
    assert isinstance(mmr, MmrRecallPolicy)
    assert mmr.candidate_k(5) == 5 * MemoryConfig().recall_pool_factor
    recency_mmr = _policy(MemoryConfig(recall="recency_mmr"))
    assert isinstance(recency_mmr, RecencyMmrRecallPolicy)
    assert recency_mmr.candidate_k(5) == 5 * MemoryConfig().recall_pool_factor
    judge = _policy(MemoryConfig(recall="judge"))  # the model rank (ADR-0038)
    assert isinstance(judge, JudgeRecallPolicy)
    assert judge.candidate_k(5) == 5 * MemoryConfig().recall_pool_factor


async def test_build_tool_registry_defaults_to_disabled() -> None:
    """The MCP-less default: no registry, and a closer that is a clean no-op."""
    registry, close = build_tool_registry(ToolsConfig(backend="none"))
    assert registry is None
    await close()  # no resources to release; must not raise


class _FakeMcpSession:
    """A fake McpSession returning canned tools, each call reporting the URL it came from."""

    def __init__(self, url: str, names: Sequence[str]) -> None:
        self._url, self._names = url, names

    async def list_tools(self) -> ListToolsResult:
        return ListToolsResult(
            tools=[Tool(name=n, description="", inputSchema={}) for n in self._names]
        )

    async def call_tool(
        self, name: str, arguments: dict[str, object] | None = None
    ) -> CallToolResult:
        del name, arguments
        return CallToolResult(content=[TextContent(type="text", text=self._url)], isError=False)


def _fake_opener(
    script: Mapping[str, Sequence[str] | BaseException], opens: list[str]
) -> Callable[[str], object]:
    """A fake `streamable_http_session`: per url it yields a canned session or raises (a down
    sidecar). ``opens`` records every dial attempt, so lazy/boot-tolerant dialing is observable."""

    @asynccontextmanager
    async def opener(url: str) -> AsyncGenerator[_FakeMcpSession, None]:
        opens.append(url)
        outcome = script[url]
        if isinstance(outcome, BaseException):
            raise outcome
        yield _FakeMcpSession(url, outcome)

    return opener


async def test_build_tool_registry_selects_mcp_and_dials_lazily(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The opt-in path dials nothing at build time (boot-tolerant, ADR-0009 addendum): the
    reconnecting registry opens a session on first use, not at construction."""
    opens: list[str] = []
    monkeypatch.setattr(
        builders_module,
        "streamable_http_session",
        _fake_opener({"http://fs:9000/mcp": ["read_text_file"]}, opens),
    )
    registry, close = build_tool_registry(ToolsConfig(backend="mcp", endpoint="http://fs:9000/mcp"))
    assert registry is not None
    assert opens == []  # no dial at build, so a sidecar down at boot does not fail the build
    names = [spec.name for spec in await registry.describe_tools()]
    assert names == ["read_text_file"]
    assert opens == ["http://fs:9000/mcp"]  # dialed on first use
    await close()  # no held session; a clean no-op


async def test_build_tool_registry_filters_and_aggregates_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Several endpoints: per-endpoint allowlists apply, and one aggregate spans them all
    in sorted-name order (ADR-0009 refinements addendum)."""
    fs_url = "http://mcp-filesystem:9000/mcp"
    mail_url = "http://mcp-email:9100/mcp"
    opens: list[str] = []
    monkeypatch.setattr(
        builders_module,
        "streamable_http_session",
        _fake_opener({fs_url: ["read_text_file", "write_file"], mail_url: ["read_email"]}, opens),
    )
    registry, close = build_tool_registry(
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
    await close()


async def test_build_tool_registry_skip_mode_serves_around_an_unavailable_sidecar(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """CORTEX_TOOLS_ON_UNAVAILABLE=skip: healthy sidecars serve, a sidecar down at boot (its dial
    fails) is mapped to ToolError, skipped, and logged (ADR-0009 boot-tolerance addendum)."""
    fs_url = "http://mcp-filesystem:9000/mcp"
    mail_url = "http://mcp-email:9100/mcp"
    opens: list[str] = []
    monkeypatch.setattr(
        builders_module,
        "streamable_http_session",
        _fake_opener({fs_url: ["read_text_file"], mail_url: httpx.ConnectError("refused")}, opens),
    )
    registry, close = build_tool_registry(
        ToolsConfig(
            backend="mcp",
            endpoints={"filesystem": fs_url, "email": mail_url},
            on_unavailable="skip",
        )
    )
    assert registry is not None
    with caplog.at_level(logging.WARNING, logger="cortex_orchestrator.builders"):
        names = [spec.name for spec in await registry.describe_tools()]
    assert names == ["read_text_file"]  # the down email sidecar is skipped, not fatal
    (record,) = caplog.records  # … and reported, never silent
    # The reporter's structured fields ride on the LogRecord as dynamic attributes.
    assert getattr(record, "sidecar", "") == "email"
    assert "MCP sidecar unavailable" in str(getattr(record, "error", ""))
    await close()


def test_build_tool_registry_tolerates_a_sidecar_down_at_build_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The boot-tolerance guarantee: building never dials, so a sidecar down at startup no longer
    fails the build. It is dialed (and skipped, if configured) only on first use (ADR-0009)."""
    opens: list[str] = []
    monkeypatch.setattr(
        builders_module,
        "streamable_http_session",
        _fake_opener({"http://down:9000/mcp": httpx.ConnectError("refused")}, opens),
    )
    registry, _ = build_tool_registry(ToolsConfig(backend="mcp", endpoint="http://down:9000/mcp"))
    assert registry is not None  # the down endpoint did not fail the build …
    assert opens == []  # … because nothing was dialed


async def test_build_subagents_defaults_to_disabled() -> None:
    """The default: no spawn tool, and a closer that is a clean no-op."""
    spawn, scheduler, close = await build_subagents(
        SubagentsConfig(backend="none"),
        None,
        "redis://x:6379/0",
        SystemClock(),
        placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.3),
    )
    assert spawn is None
    # Nothing to quiesce, so the swap conductor is handed no pool rather than an idle one.
    assert scheduler is None
    await close()  # no resources to release; must not raise


# None and an empty MCP registry both exercised: the dispatcher argument arrives None or
# real either way, assembled exactly as the composition root assembles it.
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
    spawn, scheduler, close = await build_subagents(
        config,
        build_subagent_tools(registry, SystemClock()),
        "redis://sub:6379/0",
        SystemClock(),
        placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.3),
        task_store_factory=factory,
    )
    assert isinstance(spawn, SpawnSubagentsTool)
    # The one pool object the swap conductor drains before a handoff evicts anything.
    assert isinstance(scheduler, ResourceBudgetScheduler)
    assert seen_url == ["redis://sub:6379/0"]
    await close()  # releases the fake task store + the httpx client


def _fake_task_store(url: str) -> RedisTaskStore:
    del url
    return RedisTaskStore(FakeAsyncRedis(server=FakeServer()))


def _spec_model_property(spawn: SpawnSubagentsTool) -> dict[str, object] | None:
    """Dig the per-item ``model`` property out of the advertised spawn spec (ADR-0018)."""
    instructions = cast("Mapping[str, object]", spawn.spec.parameters["properties"])
    items = cast(
        "Mapping[str, object]", cast("Mapping[str, object]", instructions["instructions"])["items"]
    )
    item_object = cast("Mapping[str, object]", cast("Sequence[object]", items["anyOf"])[1])
    properties = cast("Mapping[str, dict[str, object]]", item_object["properties"])
    return properties.get("model")


def _roster_config() -> SubagentsConfig:
    return SubagentsConfig(
        backend="llamacpp",
        endpoint="http://llama-subagent-cpu:8082",
        gpu_endpoint="http://llama-subagent-gpu:8083",
        roster={
            "qwen": SubagentRosterEntry(
                endpoint="http://llama-subagent-qwen:8084", description="small and fast"
            )
        },
    )


async def test_build_subagents_dials_its_llama_servers_under_its_own_stall_ceiling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The pool's ceiling is the subagents' own number, not the resident tier's.

    Two knobs because the worst legitimate silence differs by an order of magnitude: a CPU
    subagent decodes at a fraction of the cortex's rate, so one ceiling would have to be the
    loose one and would leave a wedged cortex stream parked for the CPU tier's allowance. The
    factory this captures is the shared one, whose read bound is asserted above.
    """
    seen: list[float] = []

    def spy(stall_timeout_s: float) -> httpx.AsyncClient:
        seen.append(stall_timeout_s)
        return builders_module.build_generation_client(stall_timeout_s)

    monkeypatch.setattr(subagent_builders_module, "build_generation_client", spy)
    _spawn, _scheduler, close = await build_subagents(
        SubagentsConfig(
            backend="llamacpp",
            endpoint="http://llama-subagent-cpu:8082",
            gpu_endpoint="http://llama-subagent-gpu:8083",
            stall_timeout_s=333.0,
        ),
        None,
        "redis://sub:6379/0",
        SystemClock(),
        placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.3),
        task_store_factory=_fake_task_store,
    )
    await close()
    # One client for the whole roster, built once with the configured seconds.
    assert seen == [333.0]


async def test_build_subagents_builds_the_config_roster_and_advertises_it() -> None:
    """A tool-less wiring with an alternate entry: the spec offers the choice (ADR-0018)."""
    spawn, _scheduler, close = await build_subagents(
        _roster_config(),
        None,  # tool-less subagents -> the model knob is advertised
        "redis://sub:6379/0",
        SystemClock(),
        placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.3),
        task_store_factory=_fake_task_store,
    )
    assert spawn is not None
    model = _spec_model_property(spawn)
    assert model is not None
    assert model["enum"] == ["qwen", "subagent"]
    description = str(model["description"])
    assert "default 'subagent'" in description  # the flat-env default entry
    assert "small and fast" in description  # the alternate's configured trade-off text
    await close()


async def test_build_subagents_with_tools_pins_the_spec_to_the_default() -> None:
    """Tools-enabled subagents: ADR-0017 rule 2b pins every spawn, so no knob is advertised."""
    spawn, _scheduler, close = await build_subagents(
        _roster_config(),
        build_subagent_tools(_read_registry(), SystemClock()),
        "redis://sub:6379/0",
        SystemClock(),
        placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.3),
        task_store_factory=_fake_task_store,
    )
    assert spawn is not None
    assert _spec_model_property(spawn) is None
    assert "default subagent model" in spawn.spec.description
    await close()


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
    roster = SubagentRoster(entries={"s": SubagentProfile(resources=resources)}, default="s")
    return SpawnSubagentsTool(SubagentRunner(store, roster, SystemClock()), store, SystemClock())


def _read_registry() -> InMemoryToolRegistry:
    return InMemoryToolRegistry(
        {"read": (ToolSpec(name="read", description="", parameters={}), _read_handler)}
    )


def test_build_subagent_tools_none_when_tools_are_disabled() -> None:
    assert build_subagent_tools(None, SystemClock()) is None


async def test_build_subagent_tools_strips_gated_tools_structurally() -> None:
    """A subagent is never handed a gated tool (ADR-0013 subagent-exclusion addendum):
    the gated name is not advertised, and invoking it anyway fails closed as not found."""
    registry = InMemoryToolRegistry(
        {
            "read": (ToolSpec(name="read", description="", parameters={}), _read_handler),
            "send": (
                ToolSpec(name="send", description="", parameters={}, gated=True),
                _read_handler,
            ),
        }
    )
    tools = build_subagent_tools(registry, SystemClock())
    assert isinstance(tools, ToolDispatcher)
    assert [spec.name for spec in await tools.describe_tools()] == ["read"]
    denied = await tools.dispatch(ToolCall(id="g1", name="send", arguments={}))
    assert denied.is_error
    assert "unknown tool 'send'" in denied.content


def test_build_output_guardrail_redact_is_the_shipped_defense() -> None:
    guard = build_output_guardrail("redact")
    assert isinstance(guard, UrlRedactingGuardrail)
    assert not isinstance(guard, StrictUrlRedactingGuardrail)


def test_build_output_guardrail_strict_is_the_opt_in_policy() -> None:
    # CORTEX_OUTPUT_GUARDRAIL=strict selects the addendum's redact-all-non-user-URL policy.
    assert isinstance(build_output_guardrail("strict"), StrictUrlRedactingGuardrail)


def test_build_output_guardrail_off_disables_it() -> None:
    # CORTEX_OUTPUT_GUARDRAIL=off is the documented off switch (ADR-0015).
    assert build_output_guardrail("off") is None


def _window(budget: int, *, summarize: bool = False) -> HistoryWindow | None:
    return build_history_window(
        BrainRuntimeConfig(history_char_budget=budget, history_summary=summarize),
        sessions=InMemorySessionStore(),
        backend=EchoInferenceBackend(),
        clock=SystemClock(),
    )


def test_build_history_window_positive_budget_enables_windowing() -> None:
    assert isinstance(_window(100), CharBudgetHistoryWindow)


def test_build_history_window_zero_disables_windowing() -> None:
    # CORTEX_HISTORY_CHAR_BUDGET=0 is the documented off switch (ADR-0014).
    assert _window(0) is None


def test_build_history_window_summarizes_when_asked() -> None:
    # CORTEX_HISTORY_SUMMARY=true wraps the budget window so dropped turns arrive as a recap.
    assert isinstance(_window(100, summarize=True), SummarizingHistoryWindow)


def test_build_history_window_ignores_the_summary_flag_without_a_budget() -> None:
    # With windowing off nothing is ever dropped, so a summarizing wrapper could never fire;
    # building one anyway would put a model call on a path that has no work for it.
    assert _window(0, summarize=True) is None


def _forty_char_turns(count: int) -> list[Message]:
    """``count`` exchanges of two 40-character messages, so a budget drops a known amount."""
    at = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)
    return [
        Message(role=role, text="x" * 40, at=at, turn_id=f"t{index}")
        for index in range(count)
        for role in (Role.USER, Role.ASSISTANT)
    ]


class _CountingBackend(EchoInferenceBackend):
    """Echo, plus a count of how many times a window actually spent a model pass."""

    def __init__(self) -> None:
        self.calls = 0

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        self.calls += 1
        async for event in super().stream(
            model, messages, tools=tools, schema=schema, bounds=bounds
        ):
            yield event


async def test_build_history_window_carries_the_fold_floor_into_the_window() -> None:
    """CORTEX_HISTORY_RECAP_MIN_CHARS is the composition root's, so it has to arrive.

    Asserted through behaviour rather than through the wrapper's private field: a floor above
    everything the budget could drop means the window makes no model call at all, which the
    scripted echo backend would otherwise answer.
    """
    backend = _CountingBackend()
    window = build_history_window(
        BrainRuntimeConfig(
            history_char_budget=200, history_summary=True, history_recap_min_chars=200
        ),
        sessions=InMemorySessionStore(),
        backend=backend,
        clock=SystemClock(),
    )
    assert isinstance(window, SummarizingHistoryWindow)
    selected = await window.select(_forty_char_turns(4), session_id="floored")
    plain = await CharBudgetHistoryWindow(200).select(_forty_char_turns(4), session_id="floored")
    assert list(selected) == list(plain)  # deferred, so no recap was prepended
    assert backend.calls == 0


async def test_build_history_window_never_lets_the_floor_exceed_the_budget() -> None:
    """A floor above the window would defer more conversation than the model can see at all.

    The same deployment as above with the floor left at a default sized for a full budget: the
    clamp brings it down to the budget, so the first boundary move that fills the window is
    paid for rather than deferred, and the recap exists at all.
    """
    backend = _CountingBackend()
    window = build_history_window(
        BrainRuntimeConfig(
            history_char_budget=80, history_summary=True, history_recap_min_chars=10_000
        ),
        sessions=InMemorySessionStore(),
        backend=backend,
        clock=SystemClock(),
    )
    assert isinstance(window, SummarizingHistoryWindow)
    await window.select(_forty_char_turns(4), session_id="clamped")
    assert backend.calls == 1  # the floor was clamped to the budget, so the fold was paid for


def test_build_cortex_tools_none_when_nothing_is_enabled() -> None:
    assert build_cortex_tools(None, (), SystemClock()) is None


async def test_build_cortex_tools_merges_the_spawn_tool_with_mcp_tools() -> None:
    tools = build_cortex_tools(_read_registry(), [_spawn_tool()], SystemClock())
    assert isinstance(tools, ToolDispatcher)
    assert {spec.name for spec in await tools.describe_tools()} == {"spawn_subagents", "read"}


async def test_build_cortex_tools_spawn_only_when_no_mcp() -> None:
    tools = build_cortex_tools(None, [_spawn_tool()], SystemClock())
    assert isinstance(tools, ToolDispatcher)
    assert {spec.name for spec in await tools.describe_tools()} == {"spawn_subagents"}


async def test_build_cortex_tools_mcp_only_when_no_subagents() -> None:
    tools = build_cortex_tools(_read_registry(), (), SystemClock())
    assert isinstance(tools, ToolDispatcher)
    assert {spec.name for spec in await tools.describe_tools()} == {"read"}


async def test_build_body_gateway_defaults_to_disabled() -> None:
    """The no-body default: no gateway, and a closer that is a clean no-op."""
    gateway, close = await build_body_gateway(BodyConfig(backend="none"), token="")
    assert gateway is None
    await close()  # no resources to release; must not raise


async def test_build_body_gateway_selects_grpc_and_returns_a_closer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The opt-in path: the endpoint, the shared seam token, and the capture deadline all
    reach GrpcBodyGateway.connect. The deadline is asserted because a knob the composition root
    silently drops leaves the suite green and the turn hanging."""
    seen: dict[str, object] = {}
    closed: list[str] = []

    async def fake_connect(
        endpoint: str, *, token: str = "", capture_timeout_s: float = 10.0
    ) -> tuple[object, Callable[[], Awaitable[None]]]:
        seen["endpoint"] = endpoint
        seen["token"] = token
        seen["capture_timeout_s"] = capture_timeout_s

        async def closer() -> None:
            closed.append("channel")

        return object(), closer

    monkeypatch.setattr(GrpcBodyGateway, "connect", fake_connect)
    gateway, close = await build_body_gateway(
        BodyConfig(backend="grpc", endpoint="host.docker.internal:50151", capture_timeout_s=2.5),
        token="s3cret",  # noqa: S106 - test seam token, not a real secret
    )
    assert gateway is not None
    assert seen == {
        "endpoint": "host.docker.internal:50151",
        "token": "s3cret",
        "capture_timeout_s": 2.5,
    }
    await close()  # closes the channel
    assert closed == ["channel"]


async def test_build_cortex_tools_adds_volume_tools_when_body_is_wired() -> None:
    tools = build_cortex_tools(
        None, build_builtin_tools(None, InMemoryBodyGateway()), SystemClock()
    )
    assert isinstance(tools, ToolDispatcher)
    advertised = {spec.name for spec in await tools.describe_tools()}
    assert advertised == {GET_VOLUME_TOOL_NAME, SET_VOLUME_TOOL_NAME}


async def test_capture_screen_is_advertised_only_when_vision_is_available() -> None:
    """It needs a body to take the picture and a model that can see it. Advertising it without
    both spends the whole privacy cost of a screen read on an image nothing can read."""
    without = build_builtin_tools(None, InMemoryBodyGateway())
    assert [tool.spec.name for tool in without] == [GET_VOLUME_TOOL_NAME, SET_VOLUME_TOOL_NAME]

    with_vision = build_builtin_tools(None, InMemoryBodyGateway(), vision=CaptureBounds())
    assert [tool.spec.name for tool in with_vision] == [
        GET_VOLUME_TOOL_NAME,
        SET_VOLUME_TOOL_NAME,
        CAPTURE_SCREEN_TOOL_NAME,
    ]

    assert build_builtin_tools(None, None, vision=CaptureBounds()) == []


async def test_the_capture_bounds_reach_the_body_through_the_built_tool() -> None:
    """A knob the composition root drops leaves the suite green and the bound unenforced, so
    the plumbing is asserted at the far end: what the body was actually asked for."""
    body = InMemoryBodyGateway()
    builtins = build_builtin_tools(
        None, body, vision=CaptureBounds(max_edge=1280, max_bytes=4_000_000)
    )
    capture = next(tool for tool in builtins if tool.spec.name == CAPTURE_SCREEN_TOOL_NAME)
    await capture.invoke(ToolCall(id="c1", name=CAPTURE_SCREEN_TOOL_NAME, arguments={}))
    assert [(ask.max_edge, ask.max_bytes) for ask in body.captures] == [(1280, 4_000_000)]


async def test_capture_screen_is_ungated_by_default() -> None:
    tools = build_cortex_tools(
        None,
        build_builtin_tools(None, InMemoryBodyGateway(), vision=CaptureBounds()),
        SystemClock(),
    )
    assert isinstance(tools, ToolDispatcher)
    gated = {spec.name: spec.gated for spec in await tools.describe_tools()}
    assert gated[CAPTURE_SCREEN_TOOL_NAME] is False


async def test_build_cortex_tools_volume_is_ungated_by_default() -> None:
    tools = build_cortex_tools(
        None, build_builtin_tools(None, InMemoryBodyGateway()), SystemClock()
    )
    assert isinstance(tools, ToolDispatcher)
    gated = {spec.name: spec.gated for spec in await tools.describe_tools()}
    assert gated == {GET_VOLUME_TOOL_NAME: False, SET_VOLUME_TOOL_NAME: False}


async def test_build_tool_registry_stamps_gated_names_at_the_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The composition-root gating overlay (ADR-0022): the remote send_email arrives
    gated=False from MCP and leaves the shared root gated=True because it is declared brain-side,
    with the default CORTEX_TOOLS_GATED covering it (fail-closed pairing)."""
    url = "http://mcp-email:9100/mcp"
    monkeypatch.setattr(
        builders_module,
        "streamable_http_session",
        _fake_opener({url: ["read_email", "send_email"]}, []),
    )
    registry, close = build_tool_registry(ToolsConfig(backend="mcp", endpoint=url))
    assert registry is not None
    gated = {spec.name: spec.gated for spec in await registry.describe_tools()}
    assert gated == {"read_email": False, "send_email": True}
    routed = await registry.invoke(ToolCall(id="c1", name="send_email", arguments={}))
    assert routed.content == url  # the overlay declares; it never blocks routing
    await close()


async def test_build_tool_registry_gated_overlay_disabled_by_an_empty_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CORTEX_TOOLS_GATED=[] is the documented off switch for the overlay."""
    url = "http://mcp-email:9100/mcp"
    monkeypatch.setattr(
        builders_module, "streamable_http_session", _fake_opener({url: ["send_email"]}, [])
    )
    registry, close = build_tool_registry(ToolsConfig(backend="mcp", endpoint=url, gated=()))
    assert registry is not None
    (spec,) = await registry.describe_tools()
    assert spec.gated is False
    await close()


async def test_build_cortex_tools_threads_the_confirmer_into_the_gate() -> None:
    """The dispatcher build_cortex_tools returns enforces ADR-0022's untainted-confirm
    branch with the confirmer it was given, so approval runs the gated tool."""
    registry = InMemoryToolRegistry(
        {"send": (ToolSpec(name="send", description="", parameters={}, gated=True), _reply_ok)}
    )
    confirmer = RecordingConfirmer(answer=True)
    tools = build_cortex_tools(registry, (), SystemClock(), confirmer=confirmer)
    assert tools is not None
    result = await tools.dispatch(
        ToolCall(id="c", name="send", arguments={}), stamp=TurnStamp(tainted=False), gated=True
    )
    assert result.is_error is False
    assert len(confirmer.requests) == 1


async def test_build_cortex_tools_defaults_to_no_confirmer_fail_closed() -> None:
    """Without a confirmer (the default), an untainted gated call is declined. This is the
    ADR-0013 fail-closed posture now covering every gated call (ADR-0022)."""
    registry = InMemoryToolRegistry(
        {"send": (ToolSpec(name="send", description="", parameters={}, gated=True), _reply_ok)}
    )
    tools = build_cortex_tools(registry, (), SystemClock())
    assert tools is not None
    result = await tools.dispatch(
        ToolCall(id="c", name="send", arguments={}), stamp=TurnStamp(tainted=False), gated=True
    )
    assert result.is_error is True
    assert result.content == USER_DECLINED_MSG


async def _reply_ok(arguments: Mapping[str, object]) -> str:
    del arguments
    return "ok"


async def test_build_cortex_tools_gated_names_gate_a_name_the_registry_advertises_ungated() -> None:
    """The wiring threads CORTEX_TOOLS_GATED into the dispatcher as the authoritative set
    (ADR-0022): a send tool the raw registry advertises ungated is still gated at dispatch,
    closing the skip-mode advertisement window."""
    registry = InMemoryToolRegistry(
        {"send_email": (ToolSpec(name="send_email", description="", parameters={}), _reply_ok)}
    )
    tools = build_cortex_tools(
        registry,
        (),
        SystemClock(),
        confirmer=RecordingConfirmer(answer=True),
        policy=DispatchPolicy(gated_names={"send_email"}),
    )
    assert tools is not None
    # The registry never stamped it gated, yet a tainted turn's call is denied outright.
    result = await tools.dispatch(
        ToolCall(id="c", name="send_email", arguments={}),
        stamp=TurnStamp(tainted=True),
        gated=False,
    )
    assert result.is_error is True
    assert result.content == DENIED_MSG


async def test_build_subagent_tools_gated_names_are_the_fail_closed_backstop() -> None:
    """A subagent dispatcher with a gated name and confirmer=None hard-denies it even if the
    UngatedToolRegistry strip were bypassed by the advertisement window (ADR-0022)."""
    registry = InMemoryToolRegistry(
        {"send_email": (ToolSpec(name="send_email", description="", parameters={}), _reply_ok)}
    )
    tools = build_subagent_tools(
        registry, SystemClock(), policy=DispatchPolicy(gated_names={"send_email"})
    )
    assert tools is not None
    result = await tools.dispatch(
        ToolCall(id="c", name="send_email", arguments={}),
        stamp=TurnStamp(tainted=False),
        gated=False,
    )
    # confirmer=None on subagents -> the gated-by-name call is declined, never run.
    assert result.is_error is True
    assert result.content == USER_DECLINED_MSG


def test_the_configured_tool_prices_reach_both_tool_loop_dispatchers() -> None:
    """CORTEX_TOOLS_COSTS threads to the cortex and to subagents (ADR-0009 cost addendum).

    Both run a `stream_tool_loop` with its own budget, so a tool a user priced has to be
    priced in delegated work too: fan-out is exactly what multiplies a cheap-looking call.
    """
    registry = InMemoryToolRegistry(
        {"read_file": (ToolSpec(name="read_file", description="", parameters={}), _reply_ok)}
    )
    policy = ToolsConfig(costs={"read_file": 5}).dispatch_policy
    cortex = build_cortex_tools(registry, (), SystemClock(), policy=policy)
    subagent = build_subagent_tools(registry, SystemClock(), policy=policy)
    assert cortex is not None
    assert subagent is not None
    assert (cortex.cost_of("read_file"), subagent.cost_of("read_file")) == (5, 5)


def test_dispatchers_built_without_prices_charge_one_per_call() -> None:
    # The default keeps the budget the plain call count it shipped as.
    registry = InMemoryToolRegistry(
        {"read_file": (ToolSpec(name="read_file", description="", parameters={}), _reply_ok)}
    )
    cortex = build_cortex_tools(registry, (), SystemClock())
    assert cortex is not None
    assert cortex.cost_of("read_file") == 1


async def test_run_from_env_with_scheduling_fires_and_shuts_down_cleanly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CORTEX_SCHEDULE_BACKEND=redis end to end at the composition root: build_schedule
    dials the (patched-to-fakeredis) URL, the ticker fires a seeded reminder, the pull RPC
    serves it, and the SIGTERM path stops the ticker cleanly before its store closes."""
    port = _free_loopback_port()
    monkeypatch.setenv("CORTEX_SEAM_HOST", "127.0.0.1")
    monkeypatch.setenv("CORTEX_SEAM_PORT", str(port))
    monkeypatch.setenv("CORTEX_SCHEDULE_BACKEND", "redis")
    monkeypatch.setenv("CORTEX_SCHEDULE_POLL_S", "0.05")
    server = FakeServer()

    def fake_from_url(url: str) -> Redis:
        del url  # every schedule-store dial lands on the shared fake server
        return FakeAsyncRedis(server=server)

    monkeypatch.setattr(Redis, "from_url", fake_from_url)
    store = RecordingStore()
    task = asyncio.create_task(run_from_env(store_factory=lambda _url: store))
    seeder = RedisScheduleStore(FakeAsyncRedis(server=server))
    now = datetime.now(UTC)
    await seeder.add(
        ScheduledItem(
            id="wired-reminder",
            kind=ScheduleKind.REMINDER,
            text="fire through the root",
            session_id="",
            due_at=now,
            created_at=now,
        )
    )
    try:
        async with aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            await asyncio.wait_for(channel.channel_ready(), timeout=10)
            stub = BrainServiceStub(channel)
            method = stub.ListDueReminders  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            fired = None
            for _ in range(100):
                reply = cast("ListDueRemindersReply", await method(ListDueRemindersRequest()))
                if reply.reminders:
                    fired = reply.reminders[0]
                    break
                await asyncio.sleep(0.02)
            assert fired is not None, "the composition-root ticker did not fire the reminder"
            assert fired.reminder_id == "wired-reminder"
        os.kill(os.getpid(), signal.SIGTERM)
        await asyncio.wait_for(task, timeout=10)  # ticker stopped, stores closed, no errors
    finally:
        task.cancel()
        await seeder.aclose()


def test_the_configured_salience_policy_reaches_both_tool_loop_dispatchers() -> None:
    """CORTEX_TOOLS_SALIENCE threads to the cortex and to subagents (salience addendum).

    Both run a `stream_tool_loop`, so a repeat has to be refused in delegated work too: a
    subagent spinning on one call is the same waste as the cortex doing it, and it is the
    cheaper mistake for a small model to make.
    """
    registry = InMemoryToolRegistry(
        {"read_file": (ToolSpec(name="read_file", description="", parameters={}), _reply_ok)}
    )
    policy = ToolsConfig(salience="off").dispatch_policy
    cortex = build_cortex_tools(registry, (), SystemClock(), policy=policy)
    subagent = build_subagent_tools(registry, SystemClock(), policy=policy)
    assert cortex is not None
    assert subagent is not None
    call = ToolCall(id="c2", name="read_file", arguments={"path": "a"})
    already = [[ToolCall(id="c1", name="read_file", arguments={"path": "a"})]]
    assert (cortex.admits(call, already), subagent.admits(call, already)) == (True, True)
    on = ToolsConfig().dispatch_policy
    strict = build_cortex_tools(registry, (), SystemClock(), policy=on)
    assert strict is not None
    assert strict.admits(call, already) is False
