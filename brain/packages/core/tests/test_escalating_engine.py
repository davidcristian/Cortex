import asyncio
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import swap_harness as harness
from swap_harness import build_harness

from cortex_core import (
    WORKING_DETAIL,
    DispatchBudget,
    EscalatingTurnEngine,
    EscalationRefs,
    EscalationSlot,
    Message,
    Role,
    StatusUpdate,
    SwapConductor,
    TaintLedger,
    TextDelta,
    TurnCompleted,
    TurnEvent,
    TurnRunner,
)

_AT = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)


class _ScriptedTurn:
    """An inner turn that streams fixed events and can fill the escalation slot as it goes."""

    def __init__(
        self,
        slot: EscalationSlot,
        *,
        events: tuple[TurnEvent, ...],
        brief: str | None = None,
        block: asyncio.Event | None = None,
    ) -> None:
        self._slot = slot
        self._events = events
        self._brief = brief
        self._block = block
        self.closed = False

    async def handle_turn(
        self, session_id: str, text: str, *, turn_id: str
    ) -> AsyncGenerator[TurnEvent, None]:
        del session_id, text, turn_id
        self._slot.refs = EscalationRefs(
            working=[Message(role=Role.USER, text=harness.USER_TEXT, at=_AT, turn_id=harness.TURN)],
            taint=TaintLedger(),
            nonce=harness.NONCE,
            budget=DispatchBudget(),
            base_len=1,
        )
        try:
            for event in self._events:
                yield event
            if self._brief is not None:
                self._slot.brief = self._brief
            if self._block is not None:
                await self._block.wait()
        finally:
            self.closed = True


def _wrapper(
    conductor: SwapConductor,
    *,
    events: tuple[TurnEvent, ...],
    brief: str | None = None,
    block: asyncio.Event | None = None,
) -> tuple[EscalatingTurnEngine, list[_ScriptedTurn]]:
    """The wrapper around a scripted inner turn, plus the list of turns it built."""
    built: list[_ScriptedTurn] = []

    def make(slot: EscalationSlot) -> TurnRunner:
        inner = _ScriptedTurn(slot, events=events, brief=brief, block=block)
        built.append(inner)
        return inner

    return EscalatingTurnEngine(make, conductor), built


async def _drain(engine: EscalatingTurnEngine) -> list[TurnEvent]:
    events: list[TurnEvent] = []
    stream = engine.handle_turn(harness.SESSION, harness.USER_TEXT, turn_id=harness.TURN)
    try:
        async for event in stream:
            events.append(event)  # noqa: PERF401 - a live stream, read one event at a time
    finally:
        await stream.aclose()
    return events


async def test_a_turn_that_does_not_escalate_is_passed_through_unchanged() -> None:
    live = build_harness()
    completed = TurnCompleted(turn_id=harness.TURN, full_text="just this")
    thinking = StatusUpdate(state="thinking", detail="hmm")
    engine, _built = _wrapper(
        live.conductor, events=(thinking, TextDelta(text="just this"), completed)
    )
    events = await _drain(engine)
    assert events == [thinking, TextDelta(text="just this"), completed]
    assert live.host.calls == []


async def test_the_escalated_turn_answers_under_the_id_it_was_asked_to_serve() -> None:
    live = build_harness()
    await live.seed_session()
    engine, _built = _wrapper(
        live.conductor,
        events=(TextDelta(text=harness.CORTEX_TEXT), TurnCompleted("an-id-of-its-own", "cortex")),
        brief=harness.BRIEF,
    )
    events = await _drain(engine)
    completions = [event for event in events if isinstance(event, TurnCompleted)]
    assert [completion.turn_id for completion in completions] == [harness.TURN]
    assert live.handoffs.deleted == [harness.TURN]


async def test_an_escalating_turn_completes_once_at_the_true_end() -> None:
    live = build_harness()
    await live.seed_session()
    engine, _built = _wrapper(
        live.conductor,
        events=(TextDelta(text=harness.CORTEX_TEXT), TurnCompleted(harness.TURN, "cortex text")),
        brief=harness.BRIEF,
    )
    events = await _drain(engine)
    completions = [event for event in events if isinstance(event, TurnCompleted)]
    assert len(completions) == 1
    assert events[-1] is completions[0]
    assert completions[0].turn_id == harness.TURN
    assert completions[0].full_text == harness.CORTEX_TEXT + "a deep answer"
    assert any(isinstance(event, StatusUpdate) for event in events)
    assert live.host.calls.count(("start", "brain")) == 1


async def test_the_wrapper_hands_the_conductor_the_turn_id_the_inner_engine_minted() -> None:
    live = build_harness()
    await live.seed_session()
    engine, _built = _wrapper(
        live.conductor,
        events=(TurnCompleted(turn_id=harness.TURN, full_text=""),),
        brief=harness.BRIEF,
    )
    await _drain(engine)
    assert live.handoffs.deleted == [harness.TURN]


async def test_closing_the_stream_mid_cortex_phase_tears_the_inner_turn_down() -> None:
    live = build_harness()
    engine, built = _wrapper(
        live.conductor, events=(TextDelta(text="thinking"),), block=asyncio.Event()
    )
    stream = engine.handle_turn(harness.SESSION, harness.USER_TEXT, turn_id=harness.TURN)
    assert await anext(stream) == TextDelta(text="thinking")
    await stream.aclose()
    assert built[0].closed is True
    assert live.host.calls == []


async def test_closing_the_stream_mid_handoff_unwinds_the_swap_at_the_wrapper_too() -> None:
    live = build_harness()
    await live.seed_session()
    engine, _built = _wrapper(
        live.conductor,
        events=(TextDelta(text=harness.CORTEX_TEXT), TurnCompleted(harness.TURN, "cortex text")),
        brief=harness.BRIEF,
    )
    stream = engine.handle_turn(harness.SESSION, harness.USER_TEXT, turn_id=harness.TURN)
    async for event in stream:
        if isinstance(event, StatusUpdate) and event.detail == WORKING_DETAIL:
            break
    assert live.host.running == {"brain"}
    await stream.aclose()
    assert live.host.running == {"cortex"}
    assert await live.handoffs.active() is None


async def test_an_inner_turn_that_never_completes_hands_nothing_off() -> None:
    live = build_harness()
    engine, _built = _wrapper(
        live.conductor, events=(TextDelta(text="cut short"),), brief=harness.BRIEF
    )
    events = await _drain(engine)
    assert events == [TextDelta(text="cut short")]
    assert live.host.calls == []
    assert await live.handoffs.active() is None
