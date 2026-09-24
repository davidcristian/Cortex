import asyncio
import json
import logging
import os
import signal
import socket
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import cast, get_args

import httpx
import pytest
from fakeredis import FakeAsyncRedis, FakeServer
from grpc import aio
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool
from redis.asyncio import Redis

import cortex_orchestrator.builders as builders_module
import cortex_orchestrator.memory_builders as memory_builders_module
import cortex_orchestrator.subagent_builders as subagent_builders_module
from cortex_body_client import GrpcBodyGateway
from cortex_core import (
    CAPTURE_SCREEN_TOOL_NAME,
    DEFAULT_CORTEX_MODEL,
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
    HashEmbedder,
    InferenceError,
    InferenceEvent,
    InMemoryBodyGateway,
    InMemorySessionStore,
    InMemoryTaskStore,
    InMemoryToolRegistry,
    JsonSchema,
    JudgeRecallPolicy,
    LookalikeUrlRedactingGuardrail,
    MemoryRecaller,
    MemoryRecord,
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
    ScoredMemory,
    ScriptedInferenceBackend,
    SessionMemoryCascade,
    SessionMemoryScope,
    SpawnSubagentsTool,
    StrictUrlRedactingGuardrail,
    SubagentAdmissionError,
    SubagentProfile,
    SubagentResources,
    SubagentRoster,
    SubagentRunner,
    SystemClock,
    TaintLedger,
    TextChunk,
    ToolCall,
    ToolDispatcher,
    ToolInvocation,
    ToolNotFoundError,
    ToolSpec,
    TurnStamp,
    UrlRedactingGuardrail,
    VramBudgetPlacer,
    record_fields,
)
from cortex_core.summarizing import SummarizingHistoryWindow
from cortex_core.windowing import HistoryWindow
from cortex_inference import LlamaCppBackend
from cortex_inference.request import TRACE_BUDGET_KEY
from cortex_memory import LoggingRecallSink, PgVectorMemoryStore
from cortex_orchestrator import (
    DEFAULT_DISPATCH_SETUP,
    BodyConfig,
    BrainRuntimeConfig,
    DispatchSetup,
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
    tool_audit_from_config,
)
from cortex_orchestrator.config import OutputGuardrailName
from cortex_orchestrator.config_subagents import DEFAULT_SUBAGENT_MODEL
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
from cortex_tools import LoggingAuditSink


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
    assert seen_urls == ["redis://redis.test.invalid:6379/5"]
    assert [m.text for m in await store.history("wired")] == ["hello", "reply 1: hello"]
    assert store.closed is True


async def test_run_from_env_default_store_surfaces_redis_outage_as_seam_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port = _free_loopback_port()
    monkeypatch.setenv("CORTEX_SEAM_HOST", "127.0.0.1")
    monkeypatch.setenv("CORTEX_SEAM_PORT", str(port))
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


async def test_the_model_a_turn_asks_for_is_the_one_its_deployment_hosts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port = _free_loopback_port()
    monkeypatch.setenv("CORTEX_SEAM_HOST", "127.0.0.1")
    monkeypatch.setenv("CORTEX_SEAM_PORT", str(port))
    monkeypatch.setenv("CORTEX_REDIS_URL", "redis://redis.test.invalid:6379/5")
    monkeypatch.setenv("CORTEX_MODEL_CORTEX", "cortex-alt")
    monkeypatch.setenv("CORTEX_INFERENCE_BACKEND", "llamacpp")
    monkeypatch.setenv("CORTEX_INFERENCE_ENDPOINT", "http://127.0.0.1:1")
    monkeypatch.setenv("CORTEX_INFERENCE_TRACE_LEVER", "off")
    store = RecordingStore()
    task = asyncio.create_task(run_from_env(store_factory=lambda _url: store))
    try:
        events = await _run_one_turn(f"127.0.0.1:{port}", "wired", "hello")
        os.kill(os.getpid(), signal.SIGTERM)
        await asyncio.wait_for(task, timeout=10)
    finally:
        task.cancel()
    (only,) = events
    assert only.WhichOneof("event") == "error"
    assert only.error.code == "inference_failed"
    assert only.error.message == "llama-server request failed for model 'cortex-alt'"


async def test_build_inference_backend_defaults_to_echo() -> None:
    backend, close = await build_inference_backend(
        InferenceConfig(backend="echo", endpoint=""), "cortex"
    )
    assert isinstance(backend, EchoInferenceBackend)
    await close()


async def test_build_inference_backend_selects_llamacpp_and_returns_a_closer() -> None:
    config = InferenceConfig(
        backend="llamacpp", endpoint="http://llama-cortex:8080", send_trace_budget="off"
    )
    backend, close = await build_inference_backend(config, "cortex")
    assert isinstance(backend, LlamaCppBackend)
    await close()


@asynccontextmanager
async def _canned_llama_server(status: int, body: str) -> AsyncGenerator[str]:
    """A loopback server answering one canned HTTP response to whatever is posted at it."""
    payload = body.encode()

    async def serve(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        while await reader.readline() not in (b"\r\n", b""):
            pass
        writer.write(
            f"HTTP/1.1 {status} x\r\nContent-Type: application/json\r\n"
            f"Content-Length: {len(payload)}\r\nConnection: close\r\n\r\n".encode()
            + payload
        )
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(serve, "127.0.0.1", 0)
    port = cast("int", server.sockets[0].getsockname()[1])
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.close()
        await server.wait_closed()


async def test_the_trace_budget_setting_is_measured_when_the_deployment_left_it_on_auto() -> None:
    refusal = '{"error":{"message":"Field \'reasoning_budget_tokens\': out of range"}}'
    async with _canned_llama_server(400, refusal) as endpoint:
        config = InferenceConfig(backend="llamacpp", endpoint=endpoint)
        assert await builders_module.resolve_send_trace_budget(config, "cortex") is True


async def test_an_engine_that_answers_the_probe_leaves_the_budget_unsent() -> None:
    async with _canned_llama_server(200, '{"choices":[]}') as endpoint:
        config = InferenceConfig(backend="llamacpp", endpoint=endpoint)
        assert await builders_module.resolve_send_trace_budget(config, "cortex") is False


async def test_the_two_fixed_modes_answer_without_asking_anything() -> None:
    # Port 1 on loopback refuses the connection at once, so nothing retries.
    dead = "http://127.0.0.1:1"
    on = InferenceConfig(backend="llamacpp", endpoint=dead, send_trace_budget="on")
    off = InferenceConfig(backend="llamacpp", endpoint=dead, send_trace_budget="off")
    assert await builders_module.resolve_send_trace_budget(on, "cortex") is True
    assert await builders_module.resolve_send_trace_budget(off, "cortex") is False


@asynccontextmanager
async def _routing_llama_server(
    serves: str,
) -> AsyncGenerator[tuple[str, list[dict[str, object]]]]:
    """A loopback server that answers by the ``model`` a request names, as a router does."""
    refusal = json.dumps({"error": {"message": f"Field '{TRACE_BUDGET_KEY}': out of range"}})
    not_found = json.dumps({"error": {"message": "model not found"}})
    completion = 'data: {"choices":[{"delta":{"content":"."}}]}\n\ndata: [DONE]\n\n'
    requests: list[dict[str, object]] = []

    async def serve(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        length = 0
        while (line := await reader.readline()) not in (b"\r\n", b""):
            name, _, value = line.decode().partition(":")
            if name.lower() == "content-length":
                length = int(value)
        request = cast("dict[str, object]", json.loads(await reader.readexactly(length)))
        requests.append(request)
        budget = request.get(TRACE_BUDGET_KEY)
        if request["model"] != serves:
            status, kind, body = 404, "application/json", not_found
        elif isinstance(budget, int) and budget < -1:
            status, kind, body = 400, "application/json", refusal
        else:
            status, kind, body = 200, "text/event-stream", completion
        payload = body.encode()
        writer.write(
            f"HTTP/1.1 {status} x\r\nContent-Type: {kind}\r\n"
            f"Content-Length: {len(payload)}\r\nConnection: close\r\n\r\n".encode()
            + payload
        )
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(serve, "127.0.0.1", 0)
    port = cast("int", server.sockets[0].getsockname()[1])
    try:
        yield f"http://127.0.0.1:{port}", requests
    finally:
        server.close()
        await server.wait_closed()


async def test_the_trace_budget_probe_asks_about_the_tier_the_deployment_named() -> None:
    async with _routing_llama_server(serves="cortex-alt") as (endpoint, requests):
        config = InferenceConfig(backend="llamacpp", endpoint=endpoint)
        backend, close = await build_inference_backend(config, "cortex-alt")
        try:
            turn = Message(role=Role.USER, text="hello", at=datetime.now(UTC), turn_id="t-1")
            bounds = GenerationBounds(max_tokens=8, thinking=False, trace_tokens=0)
            events = [event async for event in backend.stream("cortex-alt", [turn], bounds=bounds)]
        finally:
            await close()
        assert [request["model"] for request in requests] == ["cortex-alt", "cortex-alt"]
        assert requests[1][TRACE_BUDGET_KEY] == 0
        assert any(isinstance(event, TextChunk) for event in events)
        assert (
            await builders_module.resolve_send_trace_budget(config, DEFAULT_CORTEX_MODEL) is False
        )


async def test_the_generation_client_bounds_every_phase_including_the_read() -> None:
    client = builders_module.build_generation_client(45.5)
    try:
        assert client.timeout == httpx.Timeout(connect=10.0, read=45.5, write=10.0, pool=10.0)
    finally:
        await client.aclose()


@asynccontextmanager
async def _wedged_llama_server() -> AsyncGenerator[str]:
    """A loopback server that answers with the SSE headers and then never sends a chunk."""
    stop = asyncio.Event()

    async def serve_wedged(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await reader.readline()
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n\r\n")
        await writer.drain()
        await stop.wait()
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
    async with _wedged_llama_server() as endpoint:
        config = InferenceConfig(
            backend="llamacpp", endpoint=endpoint, stall_timeout_s=0.25, send_trace_budget="off"
        )
        backend, close = await build_inference_backend(config, "cortex")
        try:
            turn = Message(role=Role.USER, text="hello", at=datetime.now(UTC), turn_id="t-1")
            async with asyncio.timeout(10.0):
                with pytest.raises(InferenceError, match="sent nothing for model 'cortex'"):
                    async for _event in backend.stream("cortex", [turn]):
                        pass
        finally:
            await close()


async def test_build_memory_defaults_to_disabled() -> None:
    memory, cascade, close = await build_memory(
        MemoryConfig(backend="none"), SystemClock(), "cortex"
    )
    assert memory is None
    assert cascade is None
    await close()


async def test_build_memory_selects_pgvector_and_returns_a_closer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    memory, cascade, close = await build_memory(config, SystemClock(), "cortex")
    assert memory is not None
    assert isinstance(memory(EchoInferenceBackend()), MemoryRecaller)
    assert isinstance(cascade, SessionMemoryCascade)
    assert seen_dsn == ["postgresql://cortex@db/cortex"]
    await close()
    assert closed == ["store"]


def test_recall_audit_from_config_is_opt_in() -> None:
    assert recall_audit_from_config(MemoryConfig()) is None
    audited = recall_audit_from_config(MemoryConfig(recall_audit=True))
    assert isinstance(audited, LoggingRecallSink)


def test_tool_audit_from_config_is_the_log_line_alone_by_default() -> None:
    assert isinstance(tool_audit_from_config(ToolsConfig()), LoggingAuditSink)
    assert isinstance(DEFAULT_DISPATCH_SETUP.audit, LoggingAuditSink)


async def test_tool_audit_from_config_writes_the_line_then_the_file(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="cortex.tools.audit")
    path = tmp_path / "audit.jsonl"
    audit = tool_audit_from_config(ToolsConfig(audit_file=str(path)))
    registry = InMemoryToolRegistry(
        {"read": (ToolSpec(name="read", description="", parameters={}), _reply_ok)}
    )
    tools = build_subagent_tools(registry, SystemClock(), setup=DispatchSetup(audit=audit))
    assert tools is not None
    await tools.dispatch(
        ToolCall(id="c-1", name="read", arguments={}), stamp=TurnStamp(task_id="st")
    )
    (line,) = [record for record in caplog.records if record.name == "cortex.tools.audit"]
    (row,) = [json.loads(text) for text in path.read_text(encoding="ascii").splitlines()]
    assert (row["tool"], row["call_id"], row["task_id"]) == ("read", "c-1", "st")
    assert row == record_fields(line)


async def test_tool_audit_from_config_logs_the_call_before_its_gap(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    audit = tool_audit_from_config(ToolsConfig(audit_file=str(tmp_path / "missing" / "a.jsonl")))
    await audit.record(
        ToolInvocation(name="read", arguments={}, ok=True, detail="", at=datetime.now(UTC))
    )
    assert [record.getMessage() for record in caplog.records] == [
        "tool.invocation",
        "tool.audit.gap",
    ]


def test_memory_scope_from_name_maps_config_to_the_policy() -> None:
    assert isinstance(memory_scope_from_name("global"), GlobalMemoryScope)
    assert isinstance(memory_scope_from_name("session"), SessionMemoryScope)


def _policy(config: MemoryConfig) -> RecallPolicy:
    """`recall_policy_from_config` with the two model-rank arguments fixed."""
    return recall_policy_from_config(config, EchoInferenceBackend(), "cortex")


def test_recall_policy_from_config_maps_config_to_the_policy() -> None:
    assert isinstance(_policy(MemoryConfig()), JudgeRecallPolicy)
    assert _policy(MemoryConfig(recall="raw")) is RAW_RECALL_POLICY
    reranked = _policy(MemoryConfig(recall="reranked"))
    assert isinstance(reranked, RerankingRecallPolicy)
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
    judge = _policy(MemoryConfig(recall="judge"))
    assert isinstance(judge, JudgeRecallPolicy)
    assert judge.candidate_k(5) == 5 * MemoryConfig().recall_pool_factor


async def test_the_judge_asks_the_tier_the_deployment_named_to_rank(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    at = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)
    pool = [
        ScoredMemory(
            record=MemoryRecord(id=rid, text=rid, embedding=(1.0, 0.0), at=at), score=score
        )
        for rid, score in (("first", 0.9), ("second", 0.8))
    ]

    class PoolStore:
        """The one read a recall makes, answering the pool above, plus the closer."""

        async def search(
            self, embedding: Sequence[float], *, k: int, scopes: Sequence[str] | None = None
        ) -> Sequence[ScoredMemory]:
            del embedding, k, scopes
            return pool

        async def aclose(self) -> None:
            return None

    async def connect_pool(dsn: str) -> PoolStore:
        del dsn
        return PoolStore()

    def hash_embedder(client: httpx.AsyncClient, endpoint: str, *, model: str) -> HashEmbedder:
        del client, endpoint, model
        return HashEmbedder()

    monkeypatch.setattr(PgVectorMemoryStore, "connect", connect_pool)
    monkeypatch.setattr(memory_builders_module, "LlamaCppEmbedder", hash_embedder)
    backend = ScriptedInferenceBackend(
        [[TextChunk(text='{"order": [1, 0]}')]], serves=["cortex-alt"]
    )
    config = MemoryConfig(
        backend="pgvector",
        recall="judge",
        dsn="postgresql://cortex@db/cortex",
        embedder_endpoint="http://llama-embed:8081",
    )
    memory, _cascade, close = await build_memory(config, SystemClock(), "cortex-alt")
    assert memory is not None
    try:
        recalled = await memory(backend).recall("which?", k=2, session_id="renamed", turn_id="t")
    finally:
        await close()
    assert [hit.record.id for hit in recalled] == ["second", "first"]
    assert backend.calls == ["cortex-alt"]


async def test_build_tool_registry_defaults_to_disabled() -> None:
    registry, close = build_tool_registry(ToolsConfig(backend="none"))
    assert registry is None
    await close()


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
    sidecar).
    """

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
    opens: list[str] = []
    monkeypatch.setattr(
        builders_module,
        "streamable_http_session",
        _fake_opener({"http://fs:9000/mcp": ["read_text_file"]}, opens),
    )
    registry, close = build_tool_registry(ToolsConfig(backend="mcp", endpoint="http://fs:9000/mcp"))
    assert registry is not None
    assert opens == []
    names = [spec.name for spec in await registry.describe_tools()]
    assert names == ["read_text_file"]
    assert opens == ["http://fs:9000/mcp"]
    await close()


async def test_build_tool_registry_filters_and_aggregates_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    assert names == ["read_text_file"]
    (record,) = caplog.records
    assert getattr(record, "sidecar", "") == "email"
    assert "MCP sidecar unavailable" in str(getattr(record, "error", ""))
    await close()


# The wedged sidecar answers late rather than never, so deleting a bound fails a test here
# instead of hanging the suite. Both waits are timers on one event loop, so the bound expires
# first however loaded the machine is.
_WEDGED_BOUND_S = 0.02
_WEDGED_ANSWER_S = _WEDGED_BOUND_S * 3


class _WedgedMcpSession:
    """An McpSession that opens and then answers each call far past any bound: a wedged sidecar."""

    async def list_tools(self) -> ListToolsResult:
        await asyncio.sleep(_WEDGED_ANSWER_S)
        return ListToolsResult(tools=[])

    async def call_tool(
        self, name: str, arguments: dict[str, object] | None = None
    ) -> CallToolResult:
        del name, arguments
        await asyncio.sleep(_WEDGED_ANSWER_S)
        return CallToolResult(content=[])


async def test_build_tool_registry_bounds_a_sidecar_that_hangs(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    opens: list[str] = []

    @asynccontextmanager
    async def wedged(url: str) -> AsyncGenerator[_WedgedMcpSession, None]:
        opens.append(url)
        yield _WedgedMcpSession()

    monkeypatch.setattr(builders_module, "streamable_http_session", wedged)
    registry, close = build_tool_registry(
        ToolsConfig(
            backend="mcp",
            endpoint="http://wedged:9000/mcp",
            on_unavailable="skip",
            call_timeout_s=_WEDGED_BOUND_S,
        )
    )
    assert registry is not None
    with caplog.at_level(logging.WARNING, logger="cortex_orchestrator.builders"):
        assert list(await asyncio.wait_for(registry.describe_tools(), 10)) == []
    assert opens == ["http://wedged:9000/mcp"]
    (record,) = caplog.records
    assert getattr(record, "sidecar", "") == "default"
    assert "took longer than 0.02s" in str(getattr(record, "error", ""))
    await close()


def test_build_tool_registry_tolerates_a_sidecar_down_at_build_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opens: list[str] = []
    monkeypatch.setattr(
        builders_module,
        "streamable_http_session",
        _fake_opener({"http://down:9000/mcp": httpx.ConnectError("refused")}, opens),
    )
    registry, _ = build_tool_registry(ToolsConfig(backend="mcp", endpoint="http://down:9000/mcp"))
    assert registry is not None
    assert opens == []


async def test_build_subagents_defaults_to_disabled() -> None:
    spawn, scheduler, close = await build_subagents(
        SubagentsConfig(backend="none"),
        None,
        "redis://x:6379/0",
        SystemClock(),
        placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.3),
    )
    assert spawn is None
    assert scheduler is None
    await close()


@pytest.mark.parametrize("registry", [None, InMemoryToolRegistry({})])
async def test_build_subagents_selects_llamacpp_and_returns_a_closer(
    registry: InMemoryToolRegistry | None,
) -> None:
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
    assert isinstance(scheduler, ResourceBudgetScheduler)
    assert seen_url == ["redis://sub:6379/0"]
    await close()


def _fake_task_store(url: str) -> RedisTaskStore:
    del url
    return RedisTaskStore(FakeAsyncRedis(server=FakeServer()))


def _spec_model_property(spawn: SpawnSubagentsTool) -> dict[str, object] | None:
    """Dig the per-item ``model`` property out of the advertised spawn spec."""
    instructions = cast("Mapping[str, object]", spawn.spec.parameters["properties"])
    items = cast(
        "Mapping[str, object]", cast("Mapping[str, object]", instructions["instructions"])["items"]
    )
    item_object = cast("Mapping[str, object]", cast("Sequence[object]", items["anyOf"])[1])
    properties = cast("Mapping[str, dict[str, object]]", item_object["properties"])
    return properties.get("model")


def _roster_config(model: str = DEFAULT_SUBAGENT_MODEL) -> SubagentsConfig:
    return SubagentsConfig(
        backend="llamacpp",
        endpoint="http://llama-subagent-cpu:8082",
        gpu_endpoint="http://llama-subagent-gpu:8083",
        model=model,
        roster={
            "qwen": SubagentRosterEntry(
                endpoint="http://llama-subagent-qwen:8084", description="small and fast"
            )
        },
    )


async def test_build_subagents_dials_its_llama_servers_under_its_own_stall_ceiling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    assert seen == [333.0]


async def test_build_subagents_hands_the_pool_its_configured_admission_bound() -> None:
    _spawn, scheduler, close = await build_subagents(
        SubagentsConfig(
            backend="llamacpp",
            endpoint="http://llama-subagent-cpu:8082",
            gpu_endpoint="http://llama-subagent-gpu:8083",
            admission_wait_s=0.0,
        ),
        None,
        "redis://sub:6379/0",
        SystemClock(),
        placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.3),
        task_store_factory=_fake_task_store,
    )
    assert scheduler is not None
    whole_budget = PlacementRequest("subagent", vram_gb=3.5, cpus=4.0, memory_gb=8.0)
    async with asyncio.timeout(10.0), scheduler.admit(whole_budget):
        with pytest.raises(SubagentAdmissionError, match="waited 0s for room"):
            async with scheduler.admit(whole_budget):
                pass  # pragma: no cover - admit raises before the body runs
    await close()


@asynccontextmanager
async def _runaway_llama_server() -> AsyncGenerator[str]:
    """A loopback server that streams SSE chunks and never stops: the repetition loop itself."""
    stop = asyncio.Event()
    chunk = b'data: {"choices":[{"delta":{"content":"and also, "}}]}\n\n'

    async def serve_runaway(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await reader.readline()
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n\r\n")
        try:
            while not stop.is_set():
                writer.write(chunk)
                await writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            pass
        writer.close()

    server = await asyncio.start_server(serve_runaway, "127.0.0.1", 0)
    port = cast("int", server.sockets[0].getsockname()[1])
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        stop.set()
        server.close()
        await server.wait_closed()


async def test_a_subagent_that_never_stops_talking_is_stopped_over_a_real_socket() -> None:
    async with _runaway_llama_server() as endpoint:
        config = SubagentsConfig(
            backend="llamacpp",
            endpoint=endpoint,
            gpu_endpoint=endpoint,
            stall_timeout_s=0.5,
            run_timeout_s=1.0,
        )
        spawn, _scheduler, close = await build_subagents(
            config,
            None,
            "redis://sub:6379/0",
            SystemClock(),
            placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.3),
            task_store_factory=_fake_task_store,
        )
        assert spawn is not None
        try:
            async with asyncio.timeout(20.0):
                result = await spawn.invoke(
                    ToolCall(
                        id="c1",
                        name="spawn_subagents",
                        arguments={"instructions": ["say something short"]},
                    )
                )
        finally:
            await close()
    assert "FAILED:" in result.content
    assert "still generating after 1s" in result.content


async def test_build_subagents_builds_the_config_roster_and_advertises_it() -> None:
    spawn, _scheduler, close = await build_subagents(
        _roster_config(),
        None,
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
    assert "default 'subagent'" in description
    assert "small and fast" in description
    await close()


async def test_the_entry_every_untrusted_spawn_is_locked_to_is_one_the_roster_hosts() -> None:
    spawn, _scheduler, close = await build_subagents(
        _roster_config(model="subagent-alt"),
        None,
        "redis://sub:6379/0",
        SystemClock(),
        placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.3),
        task_store_factory=_fake_task_store,
    )
    assert spawn is not None
    model = _spec_model_property(spawn)
    assert model is not None
    assert model["enum"] == ["qwen", "subagent-alt"]
    assert "default 'subagent-alt'" in str(model["description"])
    await close()


async def test_build_subagents_with_tools_locks_the_spec_to_the_default() -> None:
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


async def test_build_subagent_tools_strips_confirm_required_tools_structurally() -> None:
    registry = InMemoryToolRegistry(
        {
            "read": (ToolSpec(name="read", description="", parameters={}), _read_handler),
            "send": (
                ToolSpec(name="send", description="", parameters={}, confirm_required=True),
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


def test_every_guarding_mode_opens_a_filter_that_logs_under_the_same_name() -> None:
    modes = [mode for mode in get_args(OutputGuardrailName) if mode != "off"]
    assert modes == ["redact", "lookalike", "strict"]
    for mode in modes:
        guard = build_output_guardrail(mode)
        assert guard is not None
        assert guard.open(TaintLedger(), allow=frozenset()).policy == mode


def test_build_output_guardrail_redact_is_the_shipped_defense() -> None:
    guard = build_output_guardrail("redact")
    assert isinstance(guard, UrlRedactingGuardrail)
    assert not isinstance(guard, StrictUrlRedactingGuardrail)


def test_build_output_guardrail_strict_is_the_opt_in_policy() -> None:
    assert isinstance(build_output_guardrail("strict"), StrictUrlRedactingGuardrail)


def test_build_output_guardrail_lookalike_is_the_homoglyph_policy() -> None:
    guard = build_output_guardrail("lookalike")
    assert isinstance(guard, LookalikeUrlRedactingGuardrail)
    assert not isinstance(guard, UrlRedactingGuardrail | StrictUrlRedactingGuardrail)


def test_build_output_guardrail_off_disables_it() -> None:
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
    assert _window(0) is None


def test_build_history_window_summarizes_when_asked() -> None:
    assert isinstance(_window(100, summarize=True), SummarizingHistoryWindow)


def test_build_history_window_ignores_the_summary_flag_without_a_budget() -> None:
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


async def test_build_history_window_passes_the_fold_floor_into_the_window() -> None:
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
    assert list(selected) == list(plain)
    assert backend.calls == 0


async def test_build_history_window_never_lets_the_floor_exceed_the_budget() -> None:
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
    assert backend.calls == 1


async def test_the_recap_is_folded_by_the_tier_the_deployment_named() -> None:
    backend = ScriptedInferenceBackend(
        [[TextChunk(text="The user and the assistant exchanged four lines of x.")]],
        serves=["cortex-alt"],
    )
    window = build_history_window(
        BrainRuntimeConfig(cortex_model="cortex-alt", history_char_budget=80, history_summary=True),
        sessions=InMemorySessionStore(),
        backend=backend,
        clock=SystemClock(),
    )
    assert isinstance(window, SummarizingHistoryWindow)
    selected = await window.select(_forty_char_turns(4), session_id="renamed")
    plain = await CharBudgetHistoryWindow(80).select(_forty_char_turns(4), session_id="renamed")
    assert len(selected) == len(plain) + 1
    assert selected[0].role is Role.SYSTEM
    assert backend.calls == ["cortex-alt"]


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
    gateway, close = await build_body_gateway(BodyConfig(backend="none"), token="")
    assert gateway is None
    await close()


async def test_build_body_gateway_selects_grpc_and_returns_a_closer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}
    closed: list[str] = []

    async def fake_connect(
        endpoint: str,
        *,
        token: str = "",
        capture_timeout_s: float = 10.0,
        call_timeout_s: float = 5.0,
    ) -> tuple[object, Callable[[], Awaitable[None]]]:
        seen["endpoint"] = endpoint
        seen["token"] = token
        seen["capture_timeout_s"] = capture_timeout_s
        seen["call_timeout_s"] = call_timeout_s

        async def closer() -> None:
            closed.append("channel")

        return object(), closer

    monkeypatch.setattr(GrpcBodyGateway, "connect", fake_connect)
    gateway, close = await build_body_gateway(
        BodyConfig(
            backend="grpc",
            endpoint="host.docker.internal:50151",
            # Two different non-default numbers, so a builder passing one for both would fail.
            capture_timeout_s=2.5,
            call_timeout_s=1.5,
        ),
        token="s3cret",  # noqa: S106 - a test token, not a real secret
    )
    assert gateway is not None
    assert seen == {
        "endpoint": "host.docker.internal:50151",
        "token": "s3cret",
        "capture_timeout_s": 2.5,
        "call_timeout_s": 1.5,
    }
    await close()
    assert closed == ["channel"]


async def test_build_cortex_tools_adds_volume_tools_when_body_is_wired() -> None:
    tools = build_cortex_tools(
        None, build_builtin_tools(None, InMemoryBodyGateway()), SystemClock()
    )
    assert isinstance(tools, ToolDispatcher)
    advertised = {spec.name for spec in await tools.describe_tools()}
    assert advertised == {GET_VOLUME_TOOL_NAME, SET_VOLUME_TOOL_NAME}


async def test_capture_screen_is_advertised_only_when_vision_is_available() -> None:
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
    body = InMemoryBodyGateway()
    builtins = build_builtin_tools(
        None, body, vision=CaptureBounds(max_edge=1280, max_bytes=4_000_000)
    )
    capture = next(tool for tool in builtins if tool.spec.name == CAPTURE_SCREEN_TOOL_NAME)
    await capture.invoke(
        ToolCall(id="c1", name=CAPTURE_SCREEN_TOOL_NAME, arguments={"target": "display"})
    )
    assert [(ask.max_edge, ask.max_bytes) for ask in body.captures] == [(1280, 4_000_000)]


async def test_capture_screen_is_confirm_free_by_default() -> None:
    tools = build_cortex_tools(
        None,
        build_builtin_tools(None, InMemoryBodyGateway(), vision=CaptureBounds()),
        SystemClock(),
    )
    assert isinstance(tools, ToolDispatcher)
    confirm_required = {spec.name: spec.confirm_required for spec in await tools.describe_tools()}
    assert confirm_required[CAPTURE_SCREEN_TOOL_NAME] is False


async def test_build_cortex_tools_volume_is_confirm_free_by_default() -> None:
    tools = build_cortex_tools(
        None, build_builtin_tools(None, InMemoryBodyGateway()), SystemClock()
    )
    assert isinstance(tools, ToolDispatcher)
    confirm_required = {spec.name: spec.confirm_required for spec in await tools.describe_tools()}
    assert confirm_required == {GET_VOLUME_TOOL_NAME: False, SET_VOLUME_TOOL_NAME: False}


async def test_build_tool_registry_stamps_confirm_names_at_the_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "http://mcp-email:9100/mcp"
    monkeypatch.setattr(
        builders_module,
        "streamable_http_session",
        _fake_opener({url: ["read_email", "send_email"]}, []),
    )
    registry, close = build_tool_registry(ToolsConfig(backend="mcp", endpoint=url))
    assert registry is not None
    confirm_required = {
        spec.name: spec.confirm_required for spec in await registry.describe_tools()
    }
    assert confirm_required == {"read_email": False, "send_email": True}
    routed = await registry.invoke(ToolCall(id="c1", name="send_email", arguments={}))
    assert routed.content == url
    await close()


async def test_build_tool_registry_confirm_required_overlay_disabled_by_an_empty_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "http://mcp-email:9100/mcp"
    monkeypatch.setattr(
        builders_module, "streamable_http_session", _fake_opener({url: ["send_email"]}, [])
    )
    registry, close = build_tool_registry(
        ToolsConfig.model_validate({"backend": "mcp", "endpoint": url, "CORTEX_TOOLS_GATED": ()})
    )
    assert registry is not None
    (spec,) = await registry.describe_tools()
    assert spec.confirm_required is False
    await close()


async def test_build_cortex_tools_threads_the_confirmer_into_the_dispatcher() -> None:
    registry = InMemoryToolRegistry(
        {
            "send": (
                ToolSpec(name="send", description="", parameters={}, confirm_required=True),
                _reply_ok,
            )
        }
    )
    confirmer = RecordingConfirmer(answer=True)
    tools = build_cortex_tools(registry, (), SystemClock(), confirmer=confirmer)
    assert tools is not None
    result = await tools.dispatch(
        ToolCall(id="c", name="send", arguments={}),
        stamp=TurnStamp(tainted=False),
        confirm_required=True,
    )
    assert result.is_error is False
    assert len(confirmer.requests) == 1


async def test_build_cortex_tools_defaults_to_no_confirmer_fail_closed() -> None:
    registry = InMemoryToolRegistry(
        {
            "send": (
                ToolSpec(name="send", description="", parameters={}, confirm_required=True),
                _reply_ok,
            )
        }
    )
    tools = build_cortex_tools(registry, (), SystemClock())
    assert tools is not None
    result = await tools.dispatch(
        ToolCall(id="c", name="send", arguments={}),
        stamp=TurnStamp(tainted=False),
        confirm_required=True,
    )
    assert result.is_error is True
    assert result.content == USER_DECLINED_MSG


async def _reply_ok(arguments: Mapping[str, object]) -> str:
    del arguments
    return "ok"


async def test_build_cortex_tools_confirm_names_confirm_a_name_advertised_as_confirm_free() -> None:
    registry = InMemoryToolRegistry(
        {"send_email": (ToolSpec(name="send_email", description="", parameters={}), _reply_ok)}
    )
    tools = build_cortex_tools(
        registry,
        (),
        SystemClock(),
        confirmer=RecordingConfirmer(answer=True),
        setup=DispatchSetup(DispatchPolicy(confirm_names={"send_email"})),
    )
    assert tools is not None
    result = await tools.dispatch(
        ToolCall(id="c", name="send_email", arguments={}),
        stamp=TurnStamp(tainted=True),
        confirm_required=False,
    )
    assert result.is_error is True
    assert result.content == DENIED_MSG


async def test_build_subagent_tools_confirm_names_are_the_fail_closed_default() -> None:
    registry = InMemoryToolRegistry(
        {"send_email": (ToolSpec(name="send_email", description="", parameters={}), _reply_ok)}
    )
    tools = build_subagent_tools(
        registry, SystemClock(), setup=DispatchSetup(DispatchPolicy(confirm_names={"send_email"}))
    )
    assert tools is not None
    result = await tools.dispatch(
        ToolCall(id="c", name="send_email", arguments={}),
        stamp=TurnStamp(tainted=False),
        confirm_required=False,
    )
    assert result.is_error is True
    assert result.content == USER_DECLINED_MSG


def test_the_configured_tool_prices_reach_both_tool_loop_dispatchers() -> None:
    registry = InMemoryToolRegistry(
        {"read_file": (ToolSpec(name="read_file", description="", parameters={}), _reply_ok)}
    )
    policy = ToolsConfig(costs={"read_file": 5}).dispatch_policy
    cortex = build_cortex_tools(registry, (), SystemClock(), setup=DispatchSetup(policy))
    subagent = build_subagent_tools(registry, SystemClock(), setup=DispatchSetup(policy))
    assert cortex is not None
    assert subagent is not None
    assert (cortex.cost_of("read_file"), subagent.cost_of("read_file")) == (5, 5)


def test_dispatchers_built_without_prices_charge_one_per_call() -> None:
    registry = InMemoryToolRegistry(
        {"read_file": (ToolSpec(name="read_file", description="", parameters={}), _reply_ok)}
    )
    cortex = build_cortex_tools(registry, (), SystemClock())
    assert cortex is not None
    assert cortex.cost_of("read_file") == 1


async def test_run_from_env_with_scheduling_fires_and_shuts_down_cleanly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port = _free_loopback_port()
    monkeypatch.setenv("CORTEX_SEAM_HOST", "127.0.0.1")
    monkeypatch.setenv("CORTEX_SEAM_PORT", str(port))
    monkeypatch.setenv("CORTEX_SCHEDULE_BACKEND", "redis")
    monkeypatch.setenv("CORTEX_SCHEDULE_POLL_S", "0.05")
    server = FakeServer()

    def fake_from_url(url: str) -> Redis:
        del url
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
        await asyncio.wait_for(task, timeout=10)
    finally:
        task.cancel()
        await seeder.aclose()


def test_the_configured_salience_policy_reaches_both_tool_loop_dispatchers() -> None:
    registry = InMemoryToolRegistry(
        {"read_file": (ToolSpec(name="read_file", description="", parameters={}), _reply_ok)}
    )
    policy = ToolsConfig(salience="off").dispatch_policy
    cortex = build_cortex_tools(registry, (), SystemClock(), setup=DispatchSetup(policy))
    subagent = build_subagent_tools(registry, SystemClock(), setup=DispatchSetup(policy))
    assert cortex is not None
    assert subagent is not None
    call = ToolCall(id="c2", name="read_file", arguments={"path": "a"})
    already = [[ToolCall(id="c1", name="read_file", arguments={"path": "a"})]]
    assert (cortex.admits(call, already), subagent.admits(call, already)) == (True, True)
    on = ToolsConfig().dispatch_policy
    strict = build_cortex_tools(registry, (), SystemClock(), setup=DispatchSetup(on))
    assert strict is not None
    assert strict.admits(call, already) is False


def test_the_configured_salience_limit_reaches_both_tool_loop_dispatchers() -> None:
    registry = InMemoryToolRegistry(
        {"read_file": (ToolSpec(name="read_file", description="", parameters={}), _reply_ok)}
    )
    policy = ToolsConfig(salience_limit=1).dispatch_policy
    cortex = build_cortex_tools(registry, (), SystemClock(), setup=DispatchSetup(policy))
    subagent = build_subagent_tools(registry, SystemClock(), setup=DispatchSetup(policy))
    assert cortex is not None
    assert subagent is not None
    call = ToolCall(id="c2", name="read_file", arguments={"path": "a"})
    already = [[ToolCall(id="c1", name="read_file", arguments={"path": "a"})], []]
    assert (cortex.admits(call, already), subagent.admits(call, already)) == (False, False)
    default = ToolsConfig().dispatch_policy
    loose = build_cortex_tools(registry, (), SystemClock(), setup=DispatchSetup(default))
    assert loose is not None
    assert loose.admits(call, already) is True
