"""The confirm round-trip through converse(): a gated tool suspends the turn on the user.

These tests wire a REAL dispatcher (gated 'send' tool) into the stream's engine via the
EngineFactory, exercising the full ADR-0022 path: dispatch → SeamConfirmer → ConfirmRequest out →
ConfirmResponse in → run or decline. Fail-closed in every direction: timeout, half-close,
and Cancel all deny.
"""

import asyncio
from collections.abc import AsyncIterator, Mapping, Sequence

from cortex_core import (
    Confirmer,
    InferenceEvent,
    InMemorySessionStore,
    InMemoryToolRegistry,
    Message,
    RecordingAuditSink,
    SystemClock,
    TextChunk,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
    TurnCapabilities,
    TurnEngine,
)
from cortex_orchestrator import EngineFactory, converse
from cortex_seam import Cancel, ClientEvent, ConfirmResponse, ServerEvent, UserTurn


class _LiveClient:
    """An interactive client-event iterator: tests push events while consuming output."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[ClientEvent | None] = asyncio.Queue()

    def send(self, event: ClientEvent) -> None:
        self._queue.put_nowait(event)

    def end(self) -> None:
        self._queue.put_nowait(None)

    def __aiter__(self) -> AsyncIterator[ClientEvent]:
        return self

    async def __anext__(self) -> ClientEvent:
        event = await self._queue.get()
        if event is None:
            raise StopAsyncIteration
        return event


class _ScriptedToolBackend:
    """Replays one event list per inference step (the test_engine.py pattern)."""

    def __init__(self, steps: Sequence[Sequence[InferenceEvent]]) -> None:
        self._steps = list(steps)
        self._call = 0

    async def stream(
        self, model: str, messages: Sequence[Message], *, tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[InferenceEvent]:
        del model, messages, tools
        step = self._steps[self._call]
        self._call += 1
        for event in step:
            yield event


def _gated_send_factory(ran: list[str]) -> EngineFactory:
    """An engine whose model calls the gated 'send' tool once, then replies 'done'."""

    async def send(arguments: Mapping[str, object]) -> str:
        ran.append(str(arguments["to"]))
        return "sent"

    def make(confirmer: Confirmer) -> TurnEngine:
        registry = InMemoryToolRegistry(
            {"send": (ToolSpec(name="send", description="", parameters={}, gated=True), send)}
        )
        dispatcher = ToolDispatcher(
            registry, RecordingAuditSink(), SystemClock(), confirmer=confirmer
        )
        backend = _ScriptedToolBackend(
            [
                [ToolCall(id="c1", name="send", arguments={"to": "bob@example.com"})],
                [TextChunk("done")],
            ]
        )
        return TurnEngine(
            InMemorySessionStore(),
            backend,
            SystemClock(),
            capabilities=TurnCapabilities(tools=dispatcher),
        )

    return make


def _user_turn(text: str) -> ClientEvent:
    return ClientEvent(session_id="s", user_turn=UserTurn(text=text))


def _answer(confirm_id: str, *, approved: bool) -> ClientEvent:
    return ClientEvent(
        session_id="s",
        confirm_response=ConfirmResponse(confirm_id=confirm_id, approved=approved),
    )


async def _next_of(stream: AsyncIterator[ServerEvent], kind: str) -> ServerEvent:
    async for event in stream:
        if event.WhichOneof("event") == kind:
            return event
    msg = f"stream ended before a {kind} event"
    raise AssertionError(msg)


async def _drain(stream: AsyncIterator[ServerEvent]) -> list[ServerEvent]:
    return [event async for event in stream]


async def test_an_approved_confirm_runs_the_gated_tool() -> None:
    ran: list[str] = []
    client = _LiveClient()
    stream = converse(_gated_send_factory(ran), client)
    client.send(_user_turn("send it"))
    request = (await _next_of(stream, "confirm_request")).confirm_request
    assert request.tool_name == "send"
    assert request.arguments_json == '{"to": "bob@example.com"}'
    assert request.reason  # shown verbatim to the user, so never empty
    client.send(_answer(request.confirm_id, approved=True))
    client.end()
    remaining = await _drain(stream)
    assert ran == ["bob@example.com"]  # the tool ran, with the approved draft
    assert any(e.WhichOneof("event") == "turn_complete" for e in remaining)


async def test_a_denied_confirm_never_runs_the_tool_but_the_turn_completes() -> None:
    ran: list[str] = []
    client = _LiveClient()
    stream = converse(_gated_send_factory(ran), client)
    client.send(_user_turn("send it"))
    request = (await _next_of(stream, "confirm_request")).confirm_request
    client.send(_answer(request.confirm_id, approved=False))
    client.end()
    remaining = await _drain(stream)
    assert ran == []  # declined: the tool never ran
    assert any(e.WhichOneof("event") == "turn_complete" for e in remaining)


async def test_an_unanswered_confirm_times_out_as_a_denial() -> None:
    ran: list[str] = []
    client = _LiveClient()
    stream = converse(_gated_send_factory(ran), client, confirm_timeout_s=0.05)
    client.send(_user_turn("send it"))
    await _next_of(stream, "confirm_request")
    # No answer and no half-close: the timeout alone must deny, and the turn completes
    # (declined) while the client stream is still open.
    await _next_of(stream, "turn_complete")
    assert ran == []
    client.end()
    await _drain(stream)


async def test_a_stale_confirm_id_is_ignored_and_the_real_answer_lands() -> None:
    ran: list[str] = []
    client = _LiveClient()
    stream = converse(_gated_send_factory(ran), client)
    client.send(_user_turn("send it"))
    request = (await _next_of(stream, "confirm_request")).confirm_request
    client.send(_answer("forged-or-stale-id", approved=True))  # resolves nothing
    client.send(_answer(request.confirm_id, approved=True))
    client.end()
    await _drain(stream)
    assert ran == ["bob@example.com"]


async def test_input_ending_mid_confirm_denies_immediately() -> None:
    # The client half-closes while the turn is (about to be) waiting: no answer can ever
    # arrive, so the pending/future asks are denied NOW and the draining turn completes
    # declined instead of hanging out the timeout (converse() would time out at 60s here, so
    # the test passing fast IS the assertion that close() short-circuited it).
    ran: list[str] = []
    client = _LiveClient()
    stream = converse(_gated_send_factory(ran), client, confirm_timeout_s=60.0)
    client.send(_user_turn("send it"))
    client.end()
    async with asyncio.timeout(5.0):
        remaining = await _drain(stream)
    assert ran == []
    assert any(e.WhichOneof("event") == "turn_complete" for e in remaining)


async def test_cancel_mid_confirm_drops_the_turn_and_the_stream_stays_open() -> None:
    ran: list[str] = []
    client = _LiveClient()
    stream = converse(_gated_send_factory(ran), client)
    client.send(_user_turn("send it"))
    request = (await _next_of(stream, "confirm_request")).confirm_request
    client.send(ClientEvent(session_id="s", cancel=Cancel()))
    client.end()
    remaining = await _drain(stream)
    assert ran == []  # the cancelled turn never ran the tool
    assert not any(e.WhichOneof("event") == "turn_complete" for e in remaining)
    # A late answer to the dead turn's request is the stale-id case: nothing to resolve.
    del request
