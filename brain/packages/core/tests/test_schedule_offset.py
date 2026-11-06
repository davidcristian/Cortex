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
from cortex_core.handoff_view import offset_refused_calls
from cortex_core.schedule_offset import (
    OFFSET_DATE_MSG,
    offset_date_wrong,
    offset_refusal,
    wanted_dates,
)
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop

_AT = datetime(2026, 11, 6, 4, 0, 0, tzinfo=UTC)
_BIRTHDAY = "Note that my mother's birthday is on 1 January, and remind me the day before."
_RIGHT = {"text": "mother's birthday tomorrow", "at_time": "09:00", "on_dates": ["12-31"]}
_WRONG_MONTH = {**_RIGHT, "on_dates": ["01-31"]}
_THE_DATE = {**_RIGHT, "on_dates": ["01-01"]}


@pytest.mark.parametrize(
    ("message", "wanted"),
    [
        (_BIRTHDAY, {"12-31"}),
        ("Our wedding anniversary is on 3 September. Remind me a week before.", {"08-27"}),
        (
            "My car insurance renews every year on 1 March; remind me two days before.",
            {"02-27", "02-28"},
        ),
        ("Our wedding anniversary is on 20 May. Remind me a week before.", {"05-13"}),
        ("The annual checkup is on June 3rd; remind me two weeks before.", {"05-20"}),
        ("The domain renewal is due Sept. 30, remind me 10 days before.", {"09-20"}),
        ("Her birthday is March 1st, remind me one day before", {"02-28", "02-29"}),
    ],
)
def test_a_reminder_before_a_yearly_date_wants_the_date_that_many_days_earlier(
    message: str, wanted: set[str]
) -> None:
    assert wanted_dates(message) == frozenset(wanted)


@pytest.mark.parametrize(
    "message",
    [
        "Note that my mother's birthday is on 1 January; remind me on the day.",
        "Our wedding anniversary is on 3 September. Remind me a week after.",
        "Remind me a week before the exam.",
        "Remind me of Anna's birthday on 11 May and of Tom's birthday on 3 June, a week before.",
        "My mother's birthday is on 30 February; remind me the day before.",
        "Our anniversary is on 3 September. Remind me a week before and the day before.",
        "Remind me on the 1st of every month, two days before rent is due, for the anniversary.",
        "Remind me the day before my mother's birthday.",
        "Remind me a week before 3 September to book the restaurant.",
        "The rent is due on 3 September and every month after; remind me a week before.",
    ],
)
def test_no_offset_no_yearly_date_two_dates_or_two_offsets_want_nothing(message: str) -> None:
    assert wanted_dates(message) == frozenset()


@pytest.mark.parametrize(
    ("name", "arguments", "query", "wrong"),
    [
        (SCHEDULE_TOOL_NAME, _RIGHT, _BIRTHDAY, False),
        (SCHEDULE_TOOL_NAME, _WRONG_MONTH, _BIRTHDAY, True),
        (SCHEDULE_TOOL_NAME, _THE_DATE, _BIRTHDAY, True),
        (SCHEDULE_TOOL_NAME, {**_RIGHT, "on_dates": ["12-31", "01-01"]}, _BIRTHDAY, True),
        (
            SCHEDULE_TOOL_NAME,
            {"at_time": "09:00", "on_dates": ["02-28"]},
            "My car insurance renews every year on 1 March; remind me two days before.",
            False,
        ),
        (
            SCHEDULE_TOOL_NAME,
            {"at_time": "09:00", "on_dates": ["05-13"]},
            "Our wedding anniversary is on 20 May. Remind me a week before.",
            False,
        ),
        (SCHEDULE_TOOL_NAME, {"at_time": "09:00", "on_month_days": [31]}, _BIRTHDAY, False),
        (SCHEDULE_TOOL_NAME, {**_RIGHT, "on_dates": ["31-12"]}, _BIRTHDAY, False),
        (SCHEDULE_TOOL_NAME, {**_RIGHT, "on_dates": "12-31"}, _BIRTHDAY, False),
        (SCHEDULE_TOOL_NAME, _THE_DATE, "Remind me on 1 January of my mother's birthday.", False),
        ("edit_scheduled", {"id": "i", **_THE_DATE}, _BIRTHDAY, False),
    ],
)
def test_only_a_schedule_call_storing_another_date_than_the_wanted_one_is_wrong(
    name: str, arguments: Mapping[str, object], query: str, *, wrong: bool
) -> None:
    call = ToolCall(id="c", name=name, arguments=arguments)
    assert offset_date_wrong(call, query) is wrong


def test_the_refusal_names_the_wanted_date_and_both_dates_before_1_march() -> None:
    assert offset_refusal(_BIRTHDAY).startswith(OFFSET_DATE_MSG)
    assert "falls on '12-31'. Call again" in offset_refusal(_BIRTHDAY)
    renewal = "My car insurance renews every year on 1 March; remind me two days before."
    assert "falls on '02-27' or '02-28'." in offset_refusal(renewal)


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


async def test_a_wrong_date_is_refused_once_with_the_wanted_date_and_the_retry_runs() -> None:
    first = ToolCall(id="c1", name=SCHEDULE_TOOL_NAME, arguments=_WRONG_MONTH)
    again = ToolCall(id="c2", name=SCHEDULE_TOOL_NAME, arguments=_THE_DATE)
    ran, audit = await _loop(_BIRTHDAY, [first, again])
    assert ran == [_THE_DATE]
    refused, kept = audit.records
    assert (refused.ok, refused.detail) == (False, OFFSET_DATE_MSG)
    assert kept.ok


async def test_the_refusal_result_the_model_reads_names_the_wanted_date() -> None:
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
        query=_BIRTHDAY,
    )
    working = [Message(role=Role.USER, text=_BIRTHDAY, at=_AT, turn_id="t")]
    call = ToolCall(id="c1", name=SCHEDULE_TOOL_NAME, arguments=_THE_DATE)
    backend = ScriptedBrainBackend(chunks=("done",), tool_calls=[call])
    _ = [event async for event in stream_tool_loop(backend, "m", working, context)]
    assert ran == []
    results = [m.text for m in working if m.role is Role.TOOL]
    assert results == [offset_refusal(_BIRTHDAY)]
    assert "'12-31'" in results[0]


@pytest.mark.parametrize(
    ("query", "arguments"),
    [
        (_BIRTHDAY, _RIGHT),
        ("Remind me on 1 January of my mother's birthday.", _THE_DATE),
        ("Our wedding anniversary is on 20 May. Remind me a week before.", {"on_dates": ["05-13"]}),
    ],
)
async def test_the_wanted_date_or_a_message_asking_no_offset_runs_at_once(
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


def test_the_calls_refused_for_a_wrong_date_are_read_from_the_tail_by_id() -> None:
    tail = (
        *_round("c0", _THE_DATE, offset_refusal(_BIRTHDAY)),
        *_round("c1", _RIGHT, "scheduled"),
    )
    record = harness.prepared_slot(tail=tail).snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=_AT
    )
    assert [call.id for call in offset_refused_calls(record)] == ["c0"]


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
        harness.SESSION, Message(role=Role.USER, text=_BIRTHDAY, at=_AT, turn_id=harness.TURN)
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


async def test_a_deep_retry_on_a_wrong_date_runs_when_the_cortex_was_refused_already() -> None:
    ran, audit = await _deep_retry(_round("c0", _THE_DATE, offset_refusal(_BIRTHDAY)), _THE_DATE)
    assert ran == [_THE_DATE]
    assert [record.ok for record in audit.records] == [True]


async def test_a_first_deep_call_on_a_wrong_date_is_refused() -> None:
    ran, audit = await _deep_retry(_round("c0", _RIGHT, "scheduled"), _WRONG_MONTH)
    assert ran == []
    assert [(record.ok, record.detail) for record in audit.records] == [(False, OFFSET_DATE_MSG)]
