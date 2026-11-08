from collections.abc import Mapping
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest
import swap_harness as harness
from swap_harness import ScriptedBrainBackend

from cortex_core import (
    SCHEDULE_TOOL_NAME,
    UTC_DISPLAY,
    DisplayZone,
    InMemorySessionStore,
    InMemoryToolRegistry,
    Message,
    RecordingAuditSink,
    Role,
    TaintLedger,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
    TurnCapabilities,
    TurnEngine,
)
from cortex_core.brain_phase import BrainPhase
from cortex_core.handoff_view import weekly_refused_calls
from cortex_core.schedule_weekly import WEEKLY_DAY_MSG, next_named_date, weekly_refusal
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop

_BERLIN = DisplayZone(name="Europe/Berlin", tz=ZoneInfo("Europe/Berlin"))
_AUCKLAND = DisplayZone(name="Pacific/Auckland", tz=ZoneInfo("Pacific/Auckland"))
_HONOLULU = DisplayZone(name="Pacific/Honolulu", tz=ZoneInfo("Pacific/Honolulu"))
# Sunday 2026-11-08, 04:00 in Berlin.
_SUNDAY = datetime(2026, 11, 8, 3, 0, tzinfo=UTC)
# Auckland is 13 hours ahead in November: 23:50 on Wednesday there, then 00:10 on Thursday.
_AUCKLAND_WED_LATE = datetime(2026, 11, 11, 10, 50, tzinfo=UTC)
_AUCKLAND_THU_EARLY = datetime(2026, 11, 11, 11, 10, tzinfo=UTC)
# Honolulu is 10 hours behind: 23:50 on Wednesday there, then 00:10 on Thursday.
_HONOLULU_WED_LATE = datetime(2026, 11, 12, 9, 50, tzinfo=UTC)
_HONOLULU_THU_EARLY = datetime(2026, 11, 12, 10, 10, tzinfo=UTC)
_DOCTOR = "Remind me on Thursday at 7 to call the doctor."
_BARBER = "Remember that I have the barber on Tuesday. Give me a shout at 8 that morning."
_LOCK_UP = "Remind me on Wednesday at 23:55 to lock up."
_THURSDAY_WEEKLY = {"text": "doctor", "at_time": "07:00", "on_days": ["thu"]}
_TUESDAY_WEEKLY = {"text": "barber", "at_time": "08:00", "on_days": ["tue"]}
_WEDNESDAY_WEEKLY = {"text": "lock up", "at_time": "23:55", "on_days": ["wed"]}
_ONCE = {"text": "lock up", "at": "2026-11-18T23:55:00"}


class _Fixed:
    def __init__(self, at: datetime) -> None:
        self._at = at

    def now(self) -> datetime:
        return self._at


@pytest.mark.parametrize(
    ("named", "at_time", "now", "zone", "expected"),
    [
        (3, "07:00", _SUNDAY, _BERLIN, date(2026, 11, 12)),
        (1, "08:00", _SUNDAY, _BERLIN, date(2026, 11, 10)),
        (0, "08:00", _SUNDAY, _BERLIN, date(2026, 11, 9)),
        (5, "08:00", _SUNDAY, _BERLIN, date(2026, 11, 14)),
        (6, "09:00", _SUNDAY, _BERLIN, date(2026, 11, 8)),
        (6, "04:01", _SUNDAY, _BERLIN, date(2026, 11, 8)),
        (6, "04:00", _SUNDAY, _BERLIN, date(2026, 11, 15)),
        (6, "03:59", _SUNDAY, _BERLIN, date(2026, 11, 15)),
        (6, "03:30", _SUNDAY, UTC_DISPLAY, date(2026, 11, 8)),
        (2, "23:55", _AUCKLAND_WED_LATE, _AUCKLAND, date(2026, 11, 11)),
        (2, "23:55", _AUCKLAND_THU_EARLY, _AUCKLAND, date(2026, 11, 18)),
        (2, "23:55", _AUCKLAND_THU_EARLY, UTC_DISPLAY, date(2026, 11, 11)),
        (3, "07:00", _AUCKLAND_WED_LATE, _AUCKLAND, date(2026, 11, 12)),
        (3, "00:15", _AUCKLAND_THU_EARLY, _AUCKLAND, date(2026, 11, 12)),
        (3, "00:05", _AUCKLAND_THU_EARLY, _AUCKLAND, date(2026, 11, 19)),
        (2, "23:55", _HONOLULU_WED_LATE, _HONOLULU, date(2026, 11, 11)),
        (2, "23:55", _HONOLULU_WED_LATE, UTC_DISPLAY, date(2026, 11, 18)),
        (2, "23:55", _HONOLULU_THU_EARLY, _HONOLULU, date(2026, 11, 18)),
        (3, "07:00", _HONOLULU_WED_LATE, _HONOLULU, date(2026, 11, 12)),
        (3, "07:00", _HONOLULU_THU_EARLY, _HONOLULU, date(2026, 11, 12)),
    ],
)
def test_the_next_date_is_today_only_while_the_time_is_ahead_in_the_zone(
    named: int, at_time: str, now: datetime, zone: DisplayZone, expected: date
) -> None:
    assert next_named_date(named, at_time, now, zone) == expected


@pytest.mark.parametrize("at_time", [None, "7am", 7, "07:00:30", "25:00", "07:00+01:00"])
def test_an_unreadable_time_names_no_date(at_time: object) -> None:
    assert next_named_date(3, at_time, _SUNDAY, _BERLIN) is None


@pytest.mark.parametrize(
    ("query", "arguments", "sentence"),
    [
        (_DOCTOR, _THURSDAY_WEEKLY, " The next Thursday is 2026-11-12."),
        (_BARBER, _TUESDAY_WEEKLY, " The next Tuesday is 2026-11-10."),
        (_BARBER, {**_TUESDAY_WEEKLY, "on_days": ["wed"]}, " The next Tuesday is 2026-11-10."),
        (
            "Erinnere mich am Donnerstag um 7 Uhr.",
            _THURSDAY_WEEKLY,
            " The next Thursday is 2026-11-12.",
        ),
    ],
)
def test_the_refusal_names_the_next_date_of_the_weekday_the_message_names(
    query: str, arguments: Mapping[str, object], sentence: str
) -> None:
    call = ToolCall(id="c", name=SCHEDULE_TOOL_NAME, arguments=arguments)
    assert weekly_refusal(call, query, _SUNDAY, _BERLIN) == WEEKLY_DAY_MSG + sentence


@pytest.mark.parametrize(
    ("query", "arguments"),
    [
        ("Remind me every Thursday at 7 to call the doctor.", _THURSDAY_WEEKLY),
        ("Remind me on Tuesday and Thursday at 7 to stretch.", _THURSDAY_WEEKLY),
        ("Remind me at 7 to call the doctor.", _THURSDAY_WEEKLY),
        (_DOCTOR, {"text": "doctor", "on_days": ["thu"]}),
        (_DOCTOR, {**_THURSDAY_WEEKLY, "at_time": "7 am"}),
    ],
)
def test_a_refusal_with_no_single_weekday_or_no_readable_time_names_no_date(
    query: str, arguments: Mapping[str, object]
) -> None:
    call = ToolCall(id="c", name=SCHEDULE_TOOL_NAME, arguments=arguments)
    assert weekly_refusal(call, query, _SUNDAY, _BERLIN) == WEEKLY_DAY_MSG


def _registry(ran: list[object]) -> InMemoryToolRegistry:
    async def handler(arguments: Mapping[str, object]) -> str:
        ran.append(dict(arguments))
        return "scheduled"

    spec = ToolSpec(name=SCHEDULE_TOOL_NAME, description="s", parameters={})
    return InMemoryToolRegistry({SCHEDULE_TOOL_NAME: (spec, handler)})


def _results(messages: list[Message]) -> list[str]:
    return [message.text for message in messages if message.role is Role.TOOL]


async def test_the_loop_names_the_date_in_its_zone_once_and_the_retry_runs() -> None:
    ran: list[object] = []
    clock = _Fixed(_AUCKLAND_THU_EARLY)
    context = ToolLoopContext(
        dispatcher=ToolDispatcher(_registry(ran), RecordingAuditSink(), clock),
        clock=clock,
        turn_id="t",
        taint=TaintLedger(),
        nonce="n",
        session_id="s",
        query=_LOCK_UP,
        zone=_AUCKLAND,
    )
    working = [Message(role=Role.USER, text=_LOCK_UP, at=_SUNDAY, turn_id="t")]
    first = ToolCall(id="c1", name=SCHEDULE_TOOL_NAME, arguments=_WEDNESDAY_WEEKLY)
    again = ToolCall(id="c2", name=SCHEDULE_TOOL_NAME, arguments=_WEDNESDAY_WEEKLY)
    backend = ScriptedBrainBackend(chunks=("done",), tool_calls=(first, again))
    _ = [event async for event in stream_tool_loop(backend, "m", working, context)]
    refused, kept = _results(working)
    assert WEEKLY_DAY_MSG in refused
    assert "The next Wednesday is 2026-11-18." in refused
    assert "scheduled" in kept
    assert "The next" not in kept
    assert ran == [_WEDNESDAY_WEEKLY]


async def test_a_turn_names_the_date_in_the_zone_its_capabilities_hold() -> None:
    ran: list[object] = []
    clock = _Fixed(_AUCKLAND_THU_EARLY)
    dispatcher = ToolDispatcher(_registry(ran), RecordingAuditSink(), clock)
    first = ToolCall(id="c1", name=SCHEDULE_TOOL_NAME, arguments=_WEDNESDAY_WEEKLY)
    backend = ScriptedBrainBackend(chunks=("done",), tool_calls=(first,))
    engine = TurnEngine(
        InMemorySessionStore(),
        backend,
        clock,
        capabilities=TurnCapabilities(tools=dispatcher, zone=_AUCKLAND),
    )
    _ = [event async for event in engine.handle_turn("s", _LOCK_UP, turn_id="t-1")]
    assert ran == []
    assert any("The next Wednesday is 2026-11-18." in said for said in _results(backend.seen))


async def test_the_deep_phase_names_the_date_in_the_zone_its_capabilities_hold() -> None:
    ran: list[object] = []
    clock = _Fixed(_AUCKLAND_THU_EARLY)
    dispatcher = ToolDispatcher(_registry(ran), RecordingAuditSink(), clock)
    sessions = InMemorySessionStore()
    await sessions.append(
        harness.SESSION, Message(role=Role.USER, text=_LOCK_UP, at=_SUNDAY, turn_id=harness.TURN)
    )
    weekly = ToolCall(id="c2", name=SCHEDULE_TOOL_NAME, arguments=_WEDNESDAY_WEEKLY)
    backend = ScriptedBrainBackend(chunks=("done",), tool_calls=(weekly,))
    caps = TurnCapabilities(tools=dispatcher, zone=_AUCKLAND)
    phase = BrainPhase(sessions, backend, clock, "brain", caps)
    once = ToolCall(id="c0", name=SCHEDULE_TOOL_NAME, arguments=_ONCE)
    tail = (
        Message(role=Role.ASSISTANT, text="", at=_SUNDAY, turn_id=harness.TURN, tool_calls=(once,)),
        Message(
            role=Role.TOOL, text="scheduled", at=_SUNDAY, turn_id=harness.TURN, tool_call_id="c0"
        ),
    )
    record = harness.prepared_slot(tail=tail).snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=_SUNDAY
    )
    events = phase.run(record)
    try:
        _ = [event async for event in events]
    finally:
        await events.aclose()
    assert ran == []
    assert any("The next Wednesday is 2026-11-18." in said for said in _results(backend.seen))


def test_a_refusal_that_names_a_date_is_still_read_from_the_tail_as_refused() -> None:
    weekly = ToolCall(id="c0", name=SCHEDULE_TOOL_NAME, arguments=_WEDNESDAY_WEEKLY)
    said = weekly_refusal(weekly, _LOCK_UP, _AUCKLAND_THU_EARLY, _AUCKLAND)
    tail = (
        Message(
            role=Role.ASSISTANT, text="", at=_SUNDAY, turn_id=harness.TURN, tool_calls=(weekly,)
        ),
        Message(role=Role.TOOL, text=said, at=_SUNDAY, turn_id=harness.TURN, tool_call_id="c0"),
    )
    record = harness.prepared_slot(tail=tail).snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=_SUNDAY
    )
    assert said != WEEKLY_DAY_MSG
    assert [call.id for call in weekly_refused_calls(record)] == ["c0"]
