"""The escalate confirm round-trip through converse(): the swap card, then the slot (ADR-0030).

These tests wire a REAL dispatcher holding the real ``EscalateToBrainTool`` into the stream's
engine via the EngineFactory, with the composition root's actual dispatch policy
(``ToolsConfig().dispatch_policy``), and drive the full in-process path over the seam:
tool call → ConfirmRequest out (carrying the app-authored swap reason, not the generic
outbound/irreversible text) → ConfirmResponse in → the slot filled (or not) → the S11.c seam
the conductor will drive, ``snapshot()`` → ``HandoffStore.put`` → one READY record. The model's
brief rides the card only as the argument draft (``arguments_json``), the existing ADR-0022
"the draft shown is the draft executed" surface; the reason line stays app-authored.
"""

import asyncio
from collections.abc import AsyncIterator, Sequence

from cortex_core import (
    ESCALATE_GATE_REASON,
    ESCALATE_TOOL_NAME,
    CompositeToolRegistry,
    Confirmer,
    EscalateToBrainTool,
    EscalationSlot,
    GenerationBounds,
    HandoffState,
    InferenceEvent,
    InMemoryHandoffStore,
    InMemorySessionStore,
    JsonSchema,
    Message,
    ProgressSink,
    RecordingAuditSink,
    SystemClock,
    TextChunk,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
    TurnCapabilities,
    TurnEngine,
)
from cortex_orchestrator import EngineFactory, ToolsConfig, converse
from cortex_seam import ClientEvent, ConfirmResponse, ServerEvent, UserTurn


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
    """Replays one event list per inference step (the test_converse_confirm.py pattern)."""

    def __init__(self, steps: Sequence[Sequence[InferenceEvent]]) -> None:
        self._steps = list(steps)
        self._call = 0

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, messages, tools, schema, bounds
        step = self._steps[self._call]
        self._call += 1
        for event in step:
            yield event


def _escalating_factory(slot: EscalationSlot) -> EngineFactory:
    """An engine whose model asks to escalate once, then wraps up with 'handing off'."""

    def make(confirmer: Confirmer, _progress: ProgressSink) -> TurnEngine:
        dispatcher = ToolDispatcher(
            CompositeToolRegistry([EscalateToBrainTool()]),
            RecordingAuditSink(),
            SystemClock(),
            confirmer=confirmer,
            # The composition root's real policy: the escalate gate backstop and the
            # app-authored per-tool card reason, exactly as the wiring builds them.
            policy=ToolsConfig().dispatch_policy,
        )
        backend = _ScriptedToolBackend(
            [
                [ToolCall(id="c1", name=ESCALATE_TOOL_NAME, arguments={"brief": "go deep"})],
                [TextChunk("handing off")],
            ]
        )
        return TurnEngine(
            InMemorySessionStore(),
            backend,
            SystemClock(),
            capabilities=TurnCapabilities(tools=dispatcher, escalation=slot),
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
    """The next event of `kind`; bounded so a missing emit fails the test, not the suite."""
    try:
        async with asyncio.timeout(5.0):
            async for event in stream:
                if event.WhichOneof("event") == kind:
                    return event
    except TimeoutError:
        msg = f"no {kind} event arrived while the stream stayed open"
        raise AssertionError(msg) from None
    msg = f"stream ended before a {kind} event"
    raise AssertionError(msg)


async def _drain(stream: AsyncIterator[ServerEvent]) -> list[ServerEvent]:
    return [event async for event in stream]


async def test_an_approved_escalation_fills_the_slot_and_snapshots_ready() -> None:
    # The full in-process path over the real converse(): the card names the tool, shows the
    # model's brief as the argument draft, and carries the app-authored swap reason; approval
    # runs the tool; the slot holds the brief; and the S11.c seam produces the READY record.
    slot = EscalationSlot()
    client = _LiveClient()
    stream = converse(_escalating_factory(slot), client)
    client.send(_user_turn("solve this properly"))
    request = (await _next_of(stream, "confirm_request")).confirm_request
    assert request.tool_name == ESCALATE_TOOL_NAME
    assert request.arguments_json == '{"brief": "go deep"}'  # the model's own words, as draft
    assert request.reason == ESCALATE_GATE_REASON  # app-authored: the swap, not "outbound"
    client.send(_answer(request.confirm_id, approved=True))
    client.end()
    remaining = await _drain(stream)
    assert any(e.WhichOneof("event") == "turn_complete" for e in remaining)
    assert slot.brief == "go deep"
    # What the conductor (the next handoff slice) does at this exact boundary:
    store = InMemoryHandoffStore()
    record = slot.snapshot(turn_id="t-esc", session_id="s", requested_at=SystemClock().now())
    await store.put(record)
    active = await store.active()
    assert active is not None
    assert (active.state, active.brief) == (HandoffState.READY, "go deep")
    assert active.rounds_used == 1  # the one escalate round, read off the captured tail


async def test_a_denied_escalation_writes_no_slot_and_no_record() -> None:
    # The user's "no" leaves nothing a later loop boundary could act on: the slot stays
    # empty, so there is nothing to snapshot and no READY record can ever exist.
    slot = EscalationSlot()
    client = _LiveClient()
    stream = converse(_escalating_factory(slot), client)
    client.send(_user_turn("solve this properly"))
    request = (await _next_of(stream, "confirm_request")).confirm_request
    client.send(_answer(request.confirm_id, approved=False))
    client.end()
    remaining = await _drain(stream)
    assert any(e.WhichOneof("event") == "turn_complete" for e in remaining)
    assert slot.brief is None
    assert slot.refs is not None  # the turn armed the slot; only the user's "no" kept it empty
