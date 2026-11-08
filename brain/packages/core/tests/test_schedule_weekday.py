from collections.abc import Mapping
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest
import swap_harness as harness
from swap_harness import ScriptedBrainBackend, TickingClock

from cortex_core import (
    SCHEDULE_TOOL_NAME,
    InMemorySessionStore,
    InMemoryToolRegistry,
    Message,
    RecordingAuditSink,
    Role,
    SystemClock,
    TaintLedger,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
    TurnCapabilities,
)
from cortex_core.brain_phase import BrainPhase
from cortex_core.handoff_view import weekday_refused_calls
from cortex_core.ports import Clock
from cortex_core.schedule_time import UTC_DISPLAY, DisplayZone
from cortex_core.schedule_verbs import EDIT_SCHEDULED_TOOL_NAME
from cortex_core.schedule_weekday import (
    WEEKDAY_DATE_MSG,
    weekday_date_wrong,
    weekday_refusal,
)
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop

_AT = datetime(2026, 11, 8, 3, 0, 0, tzinfo=UTC)
_DOCTOR = "Erinnere mich am Donnerstag um 7 Uhr an den Arzttermin."
_FRIDAY = {"text": "Arzttermin", "at": "2026-11-13T07:00:00"}
_THURSDAY = {"text": "Arzttermin", "at": "2026-11-12T07:00:00"}
_TODAY = date(2026, 11, 8)
_BERLIN = DisplayZone(name="Europe/Berlin", tz=ZoneInfo("Europe/Berlin"))
_CHAIRS = "Remind me at 6pm to return the chairs from Saturday's party."
_SUNDAY_6PM = {"text": "chairs", "at": "2026-11-08T18:00:00"}


class _BerlinMidnight:
    def now(self) -> datetime:
        return datetime(2026, 11, 7, 23, 30, tzinfo=UTC)


def _call(arguments: Mapping[str, object], name: str = SCHEDULE_TOOL_NAME) -> ToolCall:
    return ToolCall(id="c", name=name, arguments=arguments)


@pytest.mark.parametrize(
    ("message", "at"),
    [
        (_DOCTOR, "2026-11-13T07:00:00"),
        ("Remind me on Thursday at 7 to call the doctor.", "2026-11-13T07:00:00"),
        ("Remind me on Thursday morning at 7 to call the doctor.", "2026-11-13T07:00:00+01:00"),
        ("Rappelle-moi jeudi à 7h d'appeler le médecin.", "2026-11-13T07:00:00Z"),
        ("Recuérdame el jueves a las 7 llamar al médico.", "2026-11-13T07:00:00"),
        ("Amintește-mi joi la 7 să sun la doctor.", "2026-11-13T07:00:00"),
        ("Remind me on Thursday evening at 7 to call the doctor.", "2026-11-13T19:00:00"),
        ("Remind me on Thursday at 7 to call the head office.", "2026-11-13T07:00:00"),
        ("Remind me Tuesday evening at 7.", "2026-11-11T19:00:00"),
        ("Remind me at 6pm to put the bins out for Monday's collection.", "2026-11-10T18:00:00"),
    ],
)
def test_a_one_time_date_the_day_after_the_weekday_named_is_wrong(message: str, at: str) -> None:
    assert weekday_date_wrong(_call({"text": "t", "at": at}), message, _TODAY)


def test_a_date_the_day_after_the_weekday_named_is_wrong_unless_it_is_today() -> None:
    call = _call({"text": "t", "at": "2026-11-08T18:00:00"})
    message = "Remind me at 6pm to return the chairs from Saturday's party."
    assert weekday_date_wrong(call, message, date(2026, 11, 7))
    assert not weekday_date_wrong(call, message, _TODAY)


@pytest.mark.parametrize(
    ("message", "at"),
    [
        (_DOCTOR, "2026-11-12T07:00:00"),
        (_DOCTOR, "2026-11-19T07:00:00+01:00"),
        (_DOCTOR, "2026-11-11T07:00:00"),
        ("Remind me Tuesday evening at 7.", "2026-11-09T19:00:00"),
        ("Remind me on Thursday evening at 7 to call the doctor.", "2026-11-11T19:00:00"),
        ("Remind me at 6pm to put the bins out for Monday's collection.", "2026-11-08T18:00:00"),
        ("Remind me at 6pm to pack for Tuesday's trip.", "2026-11-09T18:00:00"),
        ("Remind me this evening to prepare for Monday's meeting.", "2026-11-08T19:00:00"),
        ("Rappelle-moi ce matin de préparer la réunion de lundi.", "2026-11-08T10:00:00"),
        ("Erinnere mich in einer Stunde an das Meeting am Montag.", "2026-11-08T06:30:00"),
        ("Recuérdame en una hora la reunión del lunes.", "2026-11-08T06:30:00"),
        ("Remind me at 6pm to return the chairs from Saturday's party.", "2026-11-08T18:00:00"),
        ("I work Tuesdays, remind me Friday at 8 to call mum.", "2026-11-13T08:00:00"),
        ("Note my flight on Friday, then please ring me at 6.", "2026-11-08T18:00:00"),
        ("Remind me on Thursday at 7 to call the doctor.", "2026-11-14T07:00:00"),
        ("Remind me on Thursday at 7 to call the doctor.", "2026-11-10T07:00:00"),
        ("I work Tuesdays, remind me Friday at 8 to call mum.", "2026-11-10T08:00:00"),
        ("I have the dentist on Thursday, remind me the day before at 7.", "2026-11-11T07:00:00"),
        ("Remind me two days after Thursday at 7 to pay.", "2026-11-14T07:00:00"),
        ("Remind me tomorrow at 7 about Thursday's meeting.", "2026-11-09T07:00:00"),
        ("Remind me today at 7 about Thursday's meeting.", "2026-11-08T07:00:00"),
        ("Remind me tonight about Thursday's meeting.", "2026-11-08T20:00:00"),
        ("Remind me on Thursday night at 1 to take the bins out.", "2026-11-13T01:00:00"),
        ("Remind me on Thursday at 1 to take the bins out.", "2026-11-13T01:00:00"),
        ("Remind me on Thursday at 11 pm to lock up.", "2026-11-11T23:00:00Z"),
        ("Remind me in two days, before Thursday, to pay.", "2026-11-10T07:00:00"),
        ("Remind me at 6pm the evening ahead of Thursday's meeting.", "2026-11-11T18:00:00"),
        ("Remind me beforehand about Thursday's meeting, at 7.", "2026-11-11T07:00:00"),
        ("Remind me in advance of Thursday's meeting, at 7.", "2026-11-11T07:00:00"),
        ("Remind me on Thursday at 7, and again on Friday.", "2026-11-13T07:00:00"),
        ("Remind me on Thursday and Friday at 7 to stretch.", "2026-11-13T07:00:00"),
        ("Remind me every Thursday at 7 to stretch.", "2026-11-13T07:00:00"),
        ("Remind me on 13 November, a Thursday, at 7.", "2026-11-13T07:00:00"),
        ("Remind me at 7 to call the doctor.", "2026-11-13T07:00:00"),
        ("Erinnere mich am Tag vor Donnerstag um 7 Uhr.", "2026-11-11T07:00:00"),
        ("Erinnere mich morgen an den Termin am Donnerstag.", "2026-11-09T07:00:00"),
        ("Erinnere mich am Donnerstag, den 13. November.", "2026-11-13T07:00:00"),
        ("Rappelle-moi la veille de jeudi à 7h.", "2026-11-11T07:00:00"),
        ("Rappelle-moi demain du rendez-vous de jeudi.", "2026-11-09T07:00:00"),
        ("Recuérdame el día antes del jueves a las 7.", "2026-11-11T07:00:00"),
        ("Recuérdame mañana la cita del jueves.", "2026-11-09T07:00:00"),
        ("Amintește-mi cu o zi înainte de joi la 7.", "2026-11-11T07:00:00"),
        ("Amintește-mi mâine de programarea de joi.", "2026-11-09T07:00:00"),
    ],
)
def test_the_named_weekday_the_day_before_today_a_moving_word_or_an_unclear_hour_is_not_wrong(
    message: str, at: str
) -> None:
    assert not weekday_date_wrong(_call({"text": "t", "at": at}), message, _TODAY)


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        (SCHEDULE_TOOL_NAME, {"text": "t", "at": "next Friday"}),
        (SCHEDULE_TOOL_NAME, {"text": "t", "at": 7}),
        (SCHEDULE_TOOL_NAME, {"text": "t", "in_seconds": 90}),
        (SCHEDULE_TOOL_NAME, {"text": "t", "at_time": "07:00", "on_days": ["fri"]}),
        (EDIT_SCHEDULED_TOOL_NAME, {"id": "i", "at": "2026-11-13T07:00:00"}),
    ],
)
def test_only_a_schedule_call_with_a_readable_at_is_read(
    name: str, arguments: Mapping[str, object]
) -> None:
    assert not weekday_date_wrong(_call(arguments, name), _DOCTOR, _TODAY)


def test_the_refusal_names_both_weekdays_and_the_dates_of_the_named_one_around_it() -> None:
    said = weekday_refusal(date(2026, 11, 13), 3)
    assert said.startswith(WEEKDAY_DATE_MSG)
    assert "names Thursday" in said
    assert "2026-11-13 is a Friday" in said
    assert "2026-11-12 and 2026-11-19" in said


async def _loop(
    query: str, calls: list[ToolCall], clock: Clock | None = None, zone: DisplayZone = UTC_DISPLAY
) -> tuple[list[object], list[Message]]:
    ran: list[object] = []

    async def handler(arguments: Mapping[str, object]) -> str:
        ran.append(dict(arguments))
        return "scheduled"

    spec = ToolSpec(name=SCHEDULE_TOOL_NAME, description="s", parameters={})
    registry = InMemoryToolRegistry({SCHEDULE_TOOL_NAME: (spec, handler)})
    context = ToolLoopContext(
        dispatcher=ToolDispatcher(registry, RecordingAuditSink(), TickingClock()),
        clock=clock or TickingClock(),
        turn_id="t",
        taint=TaintLedger(),
        nonce="n",
        session_id="s",
        query=query,
        zone=zone,
    )
    working = [Message(role=Role.USER, text=query, at=_AT, turn_id="t")]
    backend = ScriptedBrainBackend(chunks=("done",), tool_calls=calls)
    _ = [event async for event in stream_tool_loop(backend, "m", working, context)]
    return ran, [message for message in working if message.role is Role.TOOL]


async def test_a_wrong_weekday_is_refused_once_and_the_retry_always_runs() -> None:
    first = ToolCall(id="c1", name=SCHEDULE_TOOL_NAME, arguments=_FRIDAY)
    again = ToolCall(id="c2", name=SCHEDULE_TOOL_NAME, arguments={**_FRIDAY, "text": "again"})
    ran, results = await _loop(_DOCTOR, [first, again])
    assert ran == [{**_FRIDAY, "text": "again"}]
    assert WEEKDAY_DATE_MSG in results[0].text
    assert "2026-11-13 is a Friday" in results[0].text
    assert "scheduled" in results[1].text


@pytest.mark.parametrize(("zone", "expected"), [(_BERLIN, [_SUNDAY_6PM]), (UTC_DISPLAY, [])])
async def test_a_date_that_is_today_in_the_persons_zone_runs_at_once(
    zone: DisplayZone, expected: list[object]
) -> None:
    call = ToolCall(id="c1", name=SCHEDULE_TOOL_NAME, arguments=_SUNDAY_6PM)
    ran, _ = await _loop(_CHAIRS, [call], _BerlinMidnight(), zone)
    assert ran == expected


async def test_a_retry_on_the_named_weekday_runs_after_the_refusal() -> None:
    first = ToolCall(id="c1", name=SCHEDULE_TOOL_NAME, arguments=_FRIDAY)
    again = ToolCall(id="c2", name=SCHEDULE_TOOL_NAME, arguments=_THURSDAY)
    ran, _ = await _loop(_DOCTOR, [first, again])
    assert ran == [_THURSDAY]


@pytest.mark.parametrize(
    ("query", "arguments"),
    [
        (_DOCTOR, _THURSDAY),
        ("Erinnere mich jeden Donnerstag um 7 Uhr an den Arzttermin.", _FRIDAY),
        ("Erinnere mich am Tag vor Donnerstag um 7 Uhr.", _FRIDAY),
    ],
)
async def test_a_right_date_or_a_message_with_no_single_day_runs_at_once(
    query: str, arguments: Mapping[str, object]
) -> None:
    ran, _ = await _loop(query, [ToolCall(id="c1", name=SCHEDULE_TOOL_NAME, arguments=arguments)])
    assert ran == [dict(arguments)]


def _round(call_id: str, arguments: Mapping[str, object], said: str) -> tuple[Message, Message]:
    call = ToolCall(id=call_id, name=SCHEDULE_TOOL_NAME, arguments=arguments)
    return (
        Message(role=Role.ASSISTANT, text="", at=_AT, turn_id=harness.TURN, tool_calls=(call,)),
        Message(role=Role.TOOL, text=said, at=_AT, turn_id=harness.TURN, tool_call_id=call_id),
    )


def test_the_calls_refused_for_a_wrong_weekday_are_read_from_the_tail_by_id() -> None:
    said = weekday_refusal(date(2026, 11, 13), 3)
    tail = (*_round("c0", _FRIDAY, said), *_round("c1", _THURSDAY, "scheduled"))
    record = harness.prepared_slot(tail=tail).snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=_AT
    )
    assert [call.id for call in weekday_refused_calls(record)] == ["c0"]


async def _deep_retry(
    tail: tuple[Message, ...], retry: Mapping[str, object]
) -> tuple[list[object], RecordingAuditSink]:
    ran: list[object] = []
    audit = RecordingAuditSink()

    async def handler(arguments: Mapping[str, object]) -> str:
        ran.append(dict(arguments))
        return "scheduled"

    spec = ToolSpec(name=SCHEDULE_TOOL_NAME, description="s", parameters={})
    registry = InMemoryToolRegistry({SCHEDULE_TOOL_NAME: (spec, handler)})
    dispatcher = ToolDispatcher(registry, audit, SystemClock())
    sessions = InMemorySessionStore()
    await sessions.append(
        harness.SESSION, Message(role=Role.USER, text=_DOCTOR, at=_AT, turn_id=harness.TURN)
    )
    backend = ScriptedBrainBackend(
        chunks=("done",), tool_calls=(ToolCall(id="c2", name=SCHEDULE_TOOL_NAME, arguments=retry),)
    )
    phase = BrainPhase(
        sessions, backend, TickingClock(), "brain", TurnCapabilities(tools=dispatcher)
    )
    record = harness.prepared_slot(tail=tail).snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=_AT
    )
    events = phase.run(record)
    try:
        _ = [event async for event in events]
    finally:
        await events.aclose()
    return ran, audit


async def test_a_deep_retry_on_another_weekday_runs_when_the_cortex_was_refused_already() -> None:
    said = weekday_refusal(date(2026, 11, 13), 3)
    ran, audit = await _deep_retry(_round("c0", _FRIDAY, said), _FRIDAY)
    assert ran == [_FRIDAY]
    assert [record.ok for record in audit.records] == [True]


async def test_a_first_deep_call_on_another_weekday_is_refused() -> None:
    ran, audit = await _deep_retry(_round("c0", _THURSDAY, "scheduled"), _FRIDAY)
    assert ran == []
    assert [(record.ok, record.detail) for record in audit.records] == [(False, WEEKDAY_DATE_MSG)]
