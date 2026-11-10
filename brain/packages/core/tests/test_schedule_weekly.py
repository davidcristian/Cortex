from collections.abc import Mapping
from datetime import UTC, datetime

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
from cortex_core.handoff_view import weekly_refused_calls
from cortex_core.schedule_verbs import EDIT_SCHEDULED_TOOL_NAME
from cortex_core.schedule_weekly import (
    WEEKLY_DAY_MSG,
    names_one_weekday,
    one_named_weekday,
    weekly_unasked,
)
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop

_AT = datetime(2026, 11, 8, 3, 0, 0, tzinfo=UTC)
_BARBER = "Remember that I have the barber on Tuesday. Give me a shout at 8 that morning."
_WEEKLY = {"text": "barber", "at_time": "08:00", "on_days": ["tue"]}
_ONCE = {"text": "barber", "at": "2026-11-10T08:00:00"}


@pytest.mark.parametrize(
    "message",
    [
        _BARBER,
        "Remind me on Friday at 18:00 to call the plumber.",
        "Remind me next Thursday at 7 to renew the parking permit.",
        "Rappelle-moi mardi à 9h d'appeler le dentiste.",
        "Rappelle-moi le mardi 10 à 9h d'appeler le dentiste.",
        "Erinnere mich am Donnerstag um 7 Uhr an den Arzttermin.",
        "Recuérdame el martes a las 9 llamar al dentista.",
        "Amintește-mi marți la 9 să sun la dentist.",
        "Amintește-mi marti la 9 să sun la dentist.",
        "Remind me Tuesday morning at 8 to put the bins out.",
        "Remind me on Tuesday night to set the alarm.",
        "Rappelle-moi mardi soir, sur la deuxième étagère.",
    ],
)
def test_one_weekday_and_no_repeat_word_names_one_weekday(message: str) -> None:
    assert names_one_weekday(message)


@pytest.mark.parametrize(
    "message",
    [
        "Remind me every Tuesday at 8 to put the bins out.",
        "On Tuesdays at 8, remind me to water the plants.",
        "Remind me each Tuesday at 8 to put the bins out.",
        "Remind me weekly on Tuesday at 8 to put the bins out.",
        "Remind me on Tuesday at 8 and repeat it.",
        "Remind me on Tuesday at 8 until the end of the year.",
        "Move my bins reminder to Tuesday at 8.",
        "Change the bins reminder to Tuesday instead.",
        "Remind me on Tuesday and Thursday at 8 to stretch.",
        "Remind me at 8 to stretch.",
        "Remind me on the first Tuesday at 8 to pay the rent.",
        "Remind me on the last Friday at 8 to pay the rent.",
        "Rappelle-moi chaque mardi à 9h de sortir les poubelles.",
        "Rappelle-moi tous les mardis à 9h de sortir les poubelles.",
        "Rappelle-moi les mardis à 9h de sortir les poubelles.",
        "Rappelle-moi le mardi à 9h de sortir les poubelles.",
        "Erinnere mich jeden Dienstag um 7 Uhr an den Müll.",
        "Erinnere mich dienstags um 7 Uhr an den Müll.",
        "Erinnere mich wöchentlich am Dienstag um 7 Uhr an den Müll.",
        "Recuérdame cada martes a las 9 sacar la basura.",
        "Recuérdame los martes a las 9 sacar la basura.",
        "Amintește-mi în fiecare marți la 9 să duc gunoiul.",
        "Amintește-mi marțea la 9 să duc gunoiul.",
        "Remind me Tuesday mornings at 8 to put the bins out.",
        "Remind me on Tuesday evenings at 7 to call grandma.",
        "Remind me Tuesday nights and afternoons to stretch.",
        "Remind me on Tuesday at 8 going forward.",
        "Remind me on Tuesday at 8, ongoing.",
        "Remind me on Tuesday at 8, indefinitely.",
        "Remind me on Tuesday at 8, permanently.",
        "Remind me on Tuesday at 8, forever.",
        "Rappelle-moi un mardi sur deux à 9h de sortir les poubelles.",
    ],
)
def test_a_repeat_word_a_change_word_or_no_single_weekday_names_no_one_weekday(
    message: str,
) -> None:
    assert not names_one_weekday(message)


@pytest.mark.parametrize(
    ("message", "day"),
    [
        ("Remind me Friday at 9 to move the car.", 4),
        ("Remind me Friday at 9 to call Anna again.", 4),
        ("Move my bins reminder to Tuesday at 8.", 1),
        ("Remind me every Tuesday at 8 to put the bins out.", 1),
        ("Remind me on Tuesday and Thursday at 8 to stretch.", None),
        ("Remind me at 8 to stretch.", None),
    ],
)
def test_the_one_weekday_a_message_names_is_read_beside_any_other_word(
    message: str, day: int | None
) -> None:
    assert one_named_weekday(message) == day


@pytest.mark.parametrize(
    ("name", "arguments", "weekly"),
    [
        (SCHEDULE_TOOL_NAME, _WEEKLY, True),
        (SCHEDULE_TOOL_NAME, {"at_time": "08:00", "on_days": "tue"}, True),
        (SCHEDULE_TOOL_NAME, _ONCE, False),
        (SCHEDULE_TOOL_NAME, {"at_time": "08:00"}, False),
        (SCHEDULE_TOOL_NAME, {"at_time": "08:00", "on_dates": ["11-10"]}, False),
        (EDIT_SCHEDULED_TOOL_NAME, {"id": "i", "at_time": "08:00", "on_days": ["tue"]}, False),
    ],
)
def test_only_a_schedule_call_with_on_days_is_weekly_beside_one_named_weekday(
    name: str, arguments: Mapping[str, object], *, weekly: bool
) -> None:
    call = ToolCall(id="c", name=name, arguments=arguments)
    assert weekly_unasked(call, _BARBER) is weekly
    assert not weekly_unasked(call, "Remind me every Tuesday at 8 to see the barber.")


async def _loop(query: str, calls: list[ToolCall]) -> tuple[list[object], RecordingAuditSink]:
    ran: list[object] = []
    audit = RecordingAuditSink()

    async def handler(arguments: Mapping[str, object]) -> str:
        ran.append(dict(arguments))
        return "scheduled"

    spec = ToolSpec(name=SCHEDULE_TOOL_NAME, description="s", parameters={})
    registry = InMemoryToolRegistry({SCHEDULE_TOOL_NAME: (spec, handler)})
    context = ToolLoopContext(
        dispatcher=ToolDispatcher(registry, audit, TickingClock()),
        clock=TickingClock(),
        turn_id="t",
        taint=TaintLedger(),
        nonce="n",
        session_id="s",
        query=query,
    )
    working = [Message(role=Role.USER, text=query, at=_AT, turn_id="t")]
    backend = ScriptedBrainBackend(chunks=("done",), tool_calls=calls)
    _ = [event async for event in stream_tool_loop(backend, "m", working, context)]
    return ran, audit


async def test_a_weekly_call_beside_one_named_weekday_is_refused_once() -> None:
    first = ToolCall(id="c1", name=SCHEDULE_TOOL_NAME, arguments=_WEEKLY)
    again = ToolCall(id="c2", name=SCHEDULE_TOOL_NAME, arguments={**_WEEKLY, "text": "again"})
    ran, audit = await _loop(_BARBER, [first, again])
    assert ran == [{**_WEEKLY, "text": "again"}]
    refused, kept = audit.records
    assert (refused.ok, refused.detail) == (False, WEEKLY_DAY_MSG)
    assert kept.ok


async def test_a_one_time_retry_runs_after_the_refusal() -> None:
    first = ToolCall(id="c1", name=SCHEDULE_TOOL_NAME, arguments=_WEEKLY)
    again = ToolCall(id="c2", name=SCHEDULE_TOOL_NAME, arguments=_ONCE)
    ran, audit = await _loop(_BARBER, [first, again])
    assert ran == [_ONCE]
    assert [record.ok for record in audit.records] == [False, True]


@pytest.mark.parametrize(
    ("query", "arguments"),
    [
        ("Remind me every Tuesday at 8 to see the barber.", _WEEKLY),
        ("Erinnere mich jeden Dienstag um 8 Uhr an den Friseur.", _WEEKLY),
        (_BARBER, _ONCE),
    ],
)
async def test_an_asked_weekly_call_or_a_one_time_call_runs_at_once(
    query: str, arguments: Mapping[str, object]
) -> None:
    ran, audit = await _loop(
        query, [ToolCall(id="c1", name=SCHEDULE_TOOL_NAME, arguments=arguments)]
    )
    assert ran == [dict(arguments)]
    assert [record.ok for record in audit.records] == [True]


def _round(call_id: str, arguments: Mapping[str, object], said: str) -> tuple[Message, Message]:
    call = ToolCall(id=call_id, name=SCHEDULE_TOOL_NAME, arguments=arguments)
    return (
        Message(role=Role.ASSISTANT, text="", at=_AT, turn_id=harness.TURN, tool_calls=(call,)),
        Message(role=Role.TOOL, text=said, at=_AT, turn_id=harness.TURN, tool_call_id=call_id),
    )


def test_the_calls_refused_for_one_weekday_are_read_from_the_tail_by_id() -> None:
    tail = (*_round("c0", _WEEKLY, WEEKLY_DAY_MSG), *_round("c1", _ONCE, "scheduled"))
    record = harness.prepared_slot(tail=tail).snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=_AT
    )
    assert [call.id for call in weekly_refused_calls(record)] == ["c0"]


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
        harness.SESSION, Message(role=Role.USER, text=_BARBER, at=_AT, turn_id=harness.TURN)
    )
    backend = ScriptedBrainBackend(
        chunks=("done",), tool_calls=(ToolCall(id="c2", name=SCHEDULE_TOOL_NAME, arguments=retry),)
    )
    phase = BrainPhase(
        sessions, backend, SystemClock(), "brain", TurnCapabilities(tools=dispatcher)
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


async def test_a_deep_weekly_retry_runs_when_the_cortex_was_refused_already() -> None:
    ran, audit = await _deep_retry(_round("c0", _WEEKLY, WEEKLY_DAY_MSG), _WEEKLY)
    assert ran == [_WEEKLY]
    assert [record.ok for record in audit.records] == [True]


async def test_a_first_deep_weekly_call_beside_one_weekday_is_refused() -> None:
    ran, audit = await _deep_retry(_round("c0", _ONCE, "scheduled"), _WEEKLY)
    assert ran == []
    assert [(record.ok, record.detail) for record in audit.records] == [(False, WEEKLY_DAY_MSG)]
