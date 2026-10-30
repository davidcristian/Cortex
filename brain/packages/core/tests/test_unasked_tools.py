from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from datetime import UTC, datetime

import pytest
import swap_harness as harness
from swap_harness import ScriptedBrainBackend, TickingClock

from cortex_core import (
    NO_CADENCE_TERMS,
    SCHEDULE_TOOL_NAME,
    SET_VOLUME_TOOL_NAME,
    BrainPhase,
    GenerationBounds,
    InferenceEvent,
    InMemorySessionStore,
    InMemoryToolRegistry,
    JsonSchema,
    Message,
    RecordingAuditSink,
    Role,
    TextChunk,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
    TurnCapabilities,
    TurnEngine,
)
from cortex_core.dispatch import UNASKED_MSG
from cortex_core.unasked_tools import unasked_tools

_AT = datetime(2026, 10, 30, 4, 0, 0, tzinfo=UTC)
_BOTH = frozenset({SET_VOLUME_TOOL_NAME, SCHEDULE_TOOL_NAME})


@pytest.mark.parametrize(
    "query",
    [
        "Please remember this: I work as a nurse.",
        "Please remember this: I take the train at 7:40.",
        "Remember that my wifi router is in the hallway.",
        "Note that my mother's birthday is on 12 May.",
        "Keep in mind that I am vegetarian.",
        "Please don't forget this: my gym class is on Tuesday.",
    ],
)
def test_a_request_to_remember_a_fact_asks_for_neither_tool(query: str) -> None:
    assert unasked_tools(query) == _BOTH


@pytest.mark.parametrize(
    "query",
    [
        "Please remember this: I take my pills at 8 pm. Remind me every day at 8 pm to take them.",
        "Note that my mother's birthday is on 12 May, and remind me of it the day before.",
        "Remember to call the plumber tomorrow at 10.",
        "Please don't forget to wake me at 6.",
        "Keep in mind that I have a flight on Friday, and set an alarm for 5.",
        "Remember that my exam is on Monday; tell me before it starts.",
        "Note that the parcel comes on Friday, so don\u2019t let me forget it.",
        "Remember this: I want a notification every Sunday to water the plants.",
        "Please remember this: schedule a call with Ana on Monday.",
    ],
)
def test_a_request_to_remember_that_asks_for_a_reminder_keeps_the_schedule_tool(
    query: str,
) -> None:
    assert unasked_tools(query) == {SET_VOLUME_TOOL_NAME}


@pytest.mark.parametrize(
    "query",
    [
        "Please remember this: I like my music quiet, so turn the volume down to 20%.",
        "Keep in mind that I am in a meeting now, so please mute the sound.",
        "Please remember this: I am hard of hearing. Make it louder.",
        "Remember that the speakers are too loud at night.",
    ],
)
def test_a_request_to_remember_that_names_the_sound_keeps_the_volume_tool(query: str) -> None:
    assert unasked_tools(query) == {SCHEDULE_TOOL_NAME}


@pytest.mark.parametrize(
    "query",
    [
        "Remind me at 9 to call my mother.",
        "Turn it down a bit.",
        "My brother's name is Luca.",
        "I just remember that the bank closes at four.",
    ],
)
def test_a_message_that_asks_nothing_be_remembered_leaves_every_tool(query: str) -> None:
    assert unasked_tools(query) == frozenset()


class _Backend:
    """Keeps the tool names each request offered, and asks for ``calls`` in its first round."""

    def __init__(self, calls: Sequence[ToolCall] = ()) -> None:
        self.offered: list[list[str]] = []
        self.seen: list[Sequence[Message]] = []
        self._calls = list(calls)

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, schema, bounds
        self.offered.append([spec.name for spec in tools])
        self.seen.append(tuple(messages))
        calls, self._calls = self._calls, []
        for call in calls:
            yield call
        if not calls:
            yield TextChunk("noted")


def _dispatcher(ran: list[str], audit: RecordingAuditSink) -> ToolDispatcher:
    def tool(name: str) -> tuple[ToolSpec, Callable[[Mapping[str, object]], Awaitable[str]]]:
        async def handler(arguments: Mapping[str, object]) -> str:
            del arguments
            ran.append(name)
            return "done"

        return ToolSpec(name=name, description=name, parameters={}), handler

    names = (SET_VOLUME_TOOL_NAME, SCHEDULE_TOOL_NAME, "look")
    registry = InMemoryToolRegistry({name: tool(name) for name in names})
    return ToolDispatcher(registry, audit, TickingClock())


async def _turn(text: str, backend: _Backend) -> tuple[list[str], RecordingAuditSink]:
    ran: list[str] = []
    audit = RecordingAuditSink()
    engine = TurnEngine(
        InMemorySessionStore(),
        backend,
        TickingClock(),
        capabilities=TurnCapabilities(tools=_dispatcher(ran, audit)),
    )
    async for _event in engine.handle_turn("s", text, turn_id="t"):
        pass
    return ran, audit


async def test_a_turn_that_asks_to_remember_a_fact_is_offered_neither_tool() -> None:
    backend = _Backend()
    await _turn("Please remember this: I work as a nurse.", backend)
    assert backend.offered == [["look"]]


async def test_a_turn_that_asks_to_remember_and_for_the_sound_is_offered_the_volume() -> None:
    backend = _Backend()
    await _turn("Please remember this: I am hard of hearing. Set the volume to 80%.", backend)
    assert backend.offered == [[SET_VOLUME_TOOL_NAME, "look"]]


async def test_an_unasked_tool_called_by_name_is_refused_and_never_runs() -> None:
    call = ToolCall(id="c1", name=SET_VOLUME_TOOL_NAME, arguments={"level": 0.5})
    backend = _Backend([call, ToolCall(id="c2", name="look", arguments={})])
    ran, audit = await _turn("Please remember this: I work as a nurse.", backend)
    assert ran == ["look"]
    refused, looked = audit.records
    assert (refused.name, refused.ok, refused.detail) == (SET_VOLUME_TOOL_NAME, False, UNASKED_MSG)
    assert looked.ok
    assert UNASKED_MSG in backend.seen[1][-2].text


async def test_the_deep_phase_refuses_a_tool_its_request_to_remember_did_not_ask_for() -> None:
    sessions = InMemorySessionStore()
    text = "Please remember this: I work as a nurse."
    await sessions.append(
        harness.SESSION, Message(role=Role.USER, text=text, at=_AT, turn_id=harness.TURN)
    )
    ran: list[str] = []
    audit = RecordingAuditSink()
    backend = ScriptedBrainBackend(
        chunks=("done",),
        tool_calls=(ToolCall(id="c1", name=SCHEDULE_TOOL_NAME, arguments={}),),
    )
    caps = TurnCapabilities(tools=_dispatcher(ran, audit))
    phase = BrainPhase(sessions, backend, TickingClock(), "brain", caps, NO_CADENCE_TERMS)
    record = harness.prepared_slot().snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=_AT
    )
    events = phase.run(record)
    try:
        async for _event in events:
            pass
    finally:
        await events.aclose()
    (refused,) = audit.records
    assert (refused.name, refused.detail) == (SCHEDULE_TOOL_NAME, UNASKED_MSG)
    assert ran == []
