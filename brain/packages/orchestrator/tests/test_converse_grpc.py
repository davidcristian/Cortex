"""The Converse contract over a real loopback grpc.aio server (CI-safe, no network).

Includes THE Slice 3 acceptance test: a fresh server over the SAME store keeps the
conversation counting, because state lives only in the session store, never in the process.
"""

import asyncio
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import cast

import grpc
from fakeredis import FakeAsyncRedis, FakeServer
from grpc import aio

from cortex_core import (
    Confirmer,
    EchoInferenceBackend,
    InferenceEvent,
    InMemorySessionStore,
    InMemoryToolRegistry,
    JsonSchema,
    Message,
    ProgressSink,
    RecordingAuditSink,
    Role,
    SessionStore,
    SessionStoreError,
    SessionSummary,
    SystemClock,
    TextChunk,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
    TurnCapabilities,
    TurnEngine,
)
from cortex_core.sessions import HistoryRecap
from cortex_orchestrator import (
    ERROR_CODE_SESSION_STORE_UNAVAILABLE,
    EngineFactory,
    SeamServerConfig,
    create_server,
)
from cortex_seam import (
    BrainServiceStub,
    Cancel,
    ClientEvent,
    ConfirmResponse,
    ServerEvent,
    UserTurn,
)
from cortex_session import RedisSessionStore

# The generated stub's attributes are untyped wire code (gate-exempt, ADR-0002 d4);
# this helper pins the real call type once so every test below stays fully typed.


def _open_converse(stub: BrainServiceStub) -> aio.StreamStreamCall[ClientEvent, ServerEvent]:
    converse = stub.Converse  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return cast("aio.StreamStreamCall[ClientEvent, ServerEvent]", converse())


def _user_turn(session_id: str, text: str) -> ClientEvent:
    return ClientEvent(session_id=session_id, user_turn=UserTurn(text=text))


async def _read_remaining(
    call: aio.StreamStreamCall[ClientEvent, ServerEvent],
) -> list[ServerEvent]:
    return [event async for event in call]


def _delta_texts(events: Sequence[ServerEvent]) -> list[str]:
    return [e.text_delta.text for e in events if e.WhichOneof("event") == "text_delta"]


def _completions(events: Sequence[ServerEvent]) -> list[str]:
    return [e.turn_complete.turn_id for e in events if e.WhichOneof("event") == "turn_complete"]


async def _run_turn_over_grpc(address: str, session_id: str, text: str) -> list[ServerEvent]:
    """One whole turn over the wire: send UserTurn, close input, drain the reply."""
    async with aio.insecure_channel(address) as channel:
        call = _open_converse(BrainServiceStub(channel))
        await call.write(_user_turn(session_id, text))
        await call.done_writing()
        return await _read_remaining(call)


def _engine(store: SessionStore) -> TurnEngine:
    return TurnEngine(store, EchoInferenceBackend(), SystemClock())


async def _start_server(engine: TurnEngine, store: SessionStore) -> tuple[aio.Server, str]:
    server, port = create_server(
        SeamServerConfig(host="127.0.0.1", port=0), lambda _confirmer, _progress: engine, store
    )
    await server.start()
    return server, f"127.0.0.1:{port}"


class FailingStore:
    """SessionStore whose append raises the typed store error (the failure path)."""

    async def append(self, session_id: str, message: Message) -> None:
        del session_id, message
        msg = "redis is down"
        raise SessionStoreError(msg)

    async def history(self, session_id: str) -> Sequence[Message]:
        del session_id
        return ()

    async def list_sessions(self, *, limit: int) -> Sequence[SessionSummary]:
        del limit
        return ()

    async def set_title(self, session_id: str, title: str) -> None:
        del session_id, title

    async def delete(self, session_id: str) -> None:
        del session_id

    async def set_pinned(self, session_id: str, *, pinned: bool) -> None:
        del session_id, pinned

    async def set_recap(self, session_id: str, recap: HistoryRecap) -> None:
        del session_id, recap

    async def recap(self, session_id: str) -> HistoryRecap | None:
        del session_id
        return None


class BlockingFirstTurnBackend:
    """First call: one delta, then blocks until cancelled. Later calls: the echo script."""

    def __init__(self) -> None:
        self._echo = EchoInferenceBackend()
        self.calls = 0
        self.first_call_closed = asyncio.Event()

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        self.calls += 1
        if self.calls > 1:
            async for event in self._echo.stream(model, messages, tools=tools, schema=schema):
                yield event
            return
        try:
            yield TextChunk("cut short")
            await asyncio.sleep(3600)
        finally:
            self.first_call_closed.set()


async def test_full_turn_streams_deltas_then_turn_complete() -> None:
    store = InMemorySessionStore()
    server, address = await _start_server(_engine(store), store)
    try:
        events = await _run_turn_over_grpc(address, "s", "hello")
    finally:
        await server.stop(grace=None)
    deltas = _delta_texts(events)
    assert len(deltas) >= 3  # the dictated contract: streamed in at least 3 deltas
    assert "".join(deltas) == "reply 1: hello"
    assert _completions(events) == [events[-1].turn_complete.turn_id]
    assert events[-1].turn_complete.turn_id  # a real id, not proto's empty default


async def test_second_turn_in_the_same_session_counts_up() -> None:
    store = InMemorySessionStore()
    server, address = await _start_server(_engine(store), store)
    try:
        await _run_turn_over_grpc(address, "s", "one")
        events = await _run_turn_over_grpc(address, "s", "two")
    finally:
        await server.stop(grace=None)
    assert "".join(_delta_texts(events)) == "reply 2: two"


async def test_conversation_survives_a_server_and_deps_restart() -> None:
    """THE slice acceptance: instance B over the SAME store continues instance A's count."""
    redis_state = FakeServer()  # plays the role of the redis process: it alone survives

    def fresh_deps() -> tuple[TurnEngine, RedisSessionStore]:
        store = RedisSessionStore(FakeAsyncRedis(server=redis_state))
        return _engine(store), store

    server_a, address_a = await _start_server(*fresh_deps())
    try:
        events_a = await _run_turn_over_grpc(address_a, "e2e", "hello")
    finally:
        await server_a.stop(grace=None)  # instance A (server + store + engine) is gone

    # Between the instances: verify AND seed via a bare store handle (no engine, no
    # server), so instance B can only be right by READING the store. Hidden
    # in-process state carried across the simulated restart would still count 1.
    bare = RedisSessionStore(FakeAsyncRedis(server=redis_state))
    assert [m.text for m in await bare.history("e2e")] == ["hello", "reply 1: hello"]
    now = SystemClock().now()
    await bare.append("e2e", Message(role=Role.USER, text="offline", at=now, turn_id="oob-1"))
    await bare.append(
        "e2e", Message(role=Role.ASSISTANT, text="reply 2: offline", at=now, turn_id="oob-1")
    )
    await bare.aclose()

    server_b, address_b = await _start_server(*fresh_deps())
    try:
        events_b = await _run_turn_over_grpc(address_b, "e2e", "again")
    finally:
        await server_b.stop(grace=None)
    assert "".join(_delta_texts(events_a)) == "reply 1: hello"
    assert "".join(_delta_texts(events_b)) == "reply 3: again"  # counted across the restart


async def test_cancel_mid_generation_keeps_the_stream_usable() -> None:
    store = InMemorySessionStore()
    backend = BlockingFirstTurnBackend()
    server, address = await _start_server(TurnEngine(store, backend, SystemClock()), store)
    try:
        async with aio.insecure_channel(address) as channel:
            call = _open_converse(BrainServiceStub(channel))
            await call.write(_user_turn("s", "first"))
            responses = aiter(call)
            first = await anext(responses)
            assert first.text_delta.text == "cut short"
            await call.write(ClientEvent(session_id="s", cancel=Cancel()))
            await asyncio.wait_for(backend.first_call_closed.wait(), timeout=5)
            await call.write(_user_turn("s", "second"))
            await call.done_writing()
            events = [event async for event in responses]
    finally:
        await server.stop(grace=None)
    # The cancelled turn's user message was persisted (so n=2); its reply was dropped.
    assert "".join(_delta_texts(events)) == "reply 2: second"
    assert len(_completions(events)) == 1
    assert [(m.role, m.text) for m in await store.history("s")] == [
        (Role.USER, "first"),
        (Role.USER, "second"),
        (Role.ASSISTANT, "reply 2: second"),
    ]


async def test_store_failure_yields_seam_error_and_ends_the_stream_cleanly() -> None:
    failing = FailingStore()
    server, address = await _start_server(_engine(failing), failing)
    try:
        async with aio.insecure_channel(address) as channel:
            call = _open_converse(BrainServiceStub(channel))
            await call.write(_user_turn("s", "hello"))
            events = await _read_remaining(call)  # ends without done_writing: server closes
            assert await call.code() is grpc.StatusCode.OK  # clean end, not an RPC error
    finally:
        await server.stop(grace=None)
    (only,) = events
    assert only.WhichOneof("event") == "error"
    assert only.error.code == ERROR_CODE_SESSION_STORE_UNAVAILABLE
    assert "redis is down" in only.error.message


async def test_client_closing_without_events_ends_the_stream_empty() -> None:
    store = InMemorySessionStore()
    server, address = await _start_server(_engine(store), store)
    try:
        async with aio.insecure_channel(address) as channel:
            call = _open_converse(BrainServiceStub(channel))
            await call.done_writing()
            assert await _read_remaining(call) == []
    finally:
        await server.stop(grace=None)


async def _events_until_complete(
    call: aio.StreamStreamCall[ClientEvent, ServerEvent],
) -> list[ServerEvent]:
    """Read via read() until the turn completes, because grpc.aio forbids mixing read() with the
    iterator API on one call, and the untyped EOF sentinel stays out of the picture."""
    events: list[ServerEvent] = []
    while True:
        event = cast("ServerEvent", await call.read())
        events.append(event)
        if event.WhichOneof("event") == "turn_complete":
            return events


class _SendOnceBackend:
    """Step 1: call the gated 'send' tool; step 2: reply 'done' (per stream call count)."""

    def __init__(self) -> None:
        self._calls = 0

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, messages, tools, schema
        self._calls += 1
        if self._calls == 1:
            yield ToolCall(id="c1", name="send", arguments={"to": "bob@example.com"})
        else:
            yield TextChunk("done")


def _gated_engine_factory(ran: list[str]) -> EngineFactory:
    """A per-stream engine whose gated 'send' tool records approved runs (ADR-0022)."""

    async def send(arguments: Mapping[str, object]) -> str:
        ran.append(str(arguments["to"]))
        return "sent"

    def make(confirmer: Confirmer, _progress: ProgressSink) -> TurnEngine:
        registry = InMemoryToolRegistry(
            {"send": (ToolSpec(name="send", description="", parameters={}, gated=True), send)}
        )
        dispatcher = ToolDispatcher(
            registry, RecordingAuditSink(), SystemClock(), confirmer=confirmer
        )
        return TurnEngine(
            InMemorySessionStore(),
            _SendOnceBackend(),
            SystemClock(),
            capabilities=TurnCapabilities(tools=dispatcher),
        )

    return make


async def test_confirm_round_trips_over_the_real_wire() -> None:
    """THE ADR-0022 wire proof: ConfirmRequest out and ConfirmResponse back over real gRPC.

    The client keeps writing after the first UserTurn (the ADR-0011 deferral taken): it
    reads the mid-turn ConfirmRequest, answers approved on the same open call, and the
    gated tool runs.
    """
    ran: list[str] = []
    server, port = create_server(
        SeamServerConfig(host="127.0.0.1", port=0),
        _gated_engine_factory(ran),
        InMemorySessionStore(),
    )
    await server.start()
    try:
        async with aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            call = _open_converse(BrainServiceStub(channel))
            await call.write(_user_turn("s", "send it"))
            request = None
            while request is None:
                event = cast("ServerEvent", await call.read())
                if event.WhichOneof("event") == "confirm_request":
                    request = event.confirm_request
            assert request.tool_name == "send"
            assert request.arguments_json == '{"to": "bob@example.com"}'
            await call.write(
                ClientEvent(
                    session_id="s",
                    confirm_response=ConfirmResponse(confirm_id=request.confirm_id, approved=True),
                )
            )
            await call.done_writing()
            remaining = await _events_until_complete(call)
        assert ran == ["bob@example.com"]
        assert _completions(remaining) != []
    finally:
        await server.stop(grace=None)


async def test_denied_confirm_over_the_real_wire_never_runs_the_tool() -> None:
    ran: list[str] = []
    server, port = create_server(
        SeamServerConfig(host="127.0.0.1", port=0),
        _gated_engine_factory(ran),
        InMemorySessionStore(),
    )
    await server.start()
    try:
        async with aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            call = _open_converse(BrainServiceStub(channel))
            await call.write(_user_turn("s", "send it"))
            request = None
            while request is None:
                event = cast("ServerEvent", await call.read())
                if event.WhichOneof("event") == "confirm_request":
                    request = event.confirm_request
            await call.write(
                ClientEvent(
                    session_id="s",
                    confirm_response=ConfirmResponse(confirm_id=request.confirm_id, approved=False),
                )
            )
            await call.done_writing()
            remaining = await _events_until_complete(call)
        assert ran == []
        assert _completions(remaining) != []
    finally:
        await server.stop(grace=None)
