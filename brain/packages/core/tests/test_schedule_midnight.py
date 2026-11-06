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
from cortex_core.handoff_view import midnight_refused_calls
from cortex_core.schedule_midnight import (
    MIDNIGHT_TIME_MSG,
    midnight_unasked,
    names_midnight,
    sets_midnight,
)
from cortex_core.schedule_verbs import EDIT_SCHEDULED_TOOL_NAME
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop

_AT = datetime(2026, 11, 6, 3, 0, 0, tzinfo=UTC)
_PARCEL = "Remind me on 14 December to post the parcel."
_ONE_TIME = {"text": "post the parcel", "at": "2026-12-14T00:00:00"}
_MORNING = {"text": "post the parcel", "at": "2026-12-14T09:00:00"}


@pytest.mark.parametrize(
    "message",
    [
        "Remind me tonight at 0:00 to post the parcel.",
        "Remind me at 12 am to post the parcel.",
        "Remind me at midnight to post the parcel.",
        "Remind me on 14 December at 00:00 to post the parcel.",
        "Remind me at 12:00 am on 14 December to post the parcel.",
        "Remind me at 12am to post the parcel.",
        "Remind me at 12 a.m. to post the parcel.",
    ],
)
def test_a_message_naming_midnight_in_any_form_names_midnight(message: str) -> None:
    assert names_midnight(message)


@pytest.mark.parametrize(
    "message",
    [
        "Remind me at 12 pm to post the parcel.",
        "Remind me at 12:00 pm to post the parcel.",
        "Remind me at 12:00 to post the parcel.",
        "Remind me at 10:00 to post the parcel.",
        "Remind me at 00:00 pm to post the parcel.",
        _PARCEL,
        "Remind me every Monday to take the bins out.",
    ],
)
def test_noon_another_time_or_no_time_does_not_name_midnight(message: str) -> None:
    assert not names_midnight(message)


@pytest.mark.parametrize(
    ("name", "arguments", "midnight"),
    [
        (SCHEDULE_TOOL_NAME, _ONE_TIME, True),
        (SCHEDULE_TOOL_NAME, {"at": "2026-12-14T00:00:00Z"}, True),
        (SCHEDULE_TOOL_NAME, {"at": "2026-12-14T00:00+01:00"}, True),
        (SCHEDULE_TOOL_NAME, {"at": "2026-12-14 00:00"}, True),
        (SCHEDULE_TOOL_NAME, {"at_time": "00:00", "on_dates": ["08-09"]}, True),
        (SCHEDULE_TOOL_NAME, {"at_time": "0:00", "on_days": ["mon"]}, True),
        (EDIT_SCHEDULED_TOOL_NAME, {"id": "i", "at_time": "00:00"}, True),
        (SCHEDULE_TOOL_NAME, _MORNING, False),
        (SCHEDULE_TOOL_NAME, {"at": "2026-12-14T00:30:00"}, False),
        (SCHEDULE_TOOL_NAME, {"at": "2026-12-14T10:00:00"}, False),
        (SCHEDULE_TOOL_NAME, {"at": "2026-12-14T00:00:00", "at_time": 0}, True),
        (SCHEDULE_TOOL_NAME, {"at_time": "09:00", "on_days": ["mon"]}, False),
        (SCHEDULE_TOOL_NAME, {"at": 0, "at_time": None}, False),
        (SCHEDULE_TOOL_NAME, {"in_seconds": 60}, False),
        (EDIT_SCHEDULED_TOOL_NAME, {"id": "i", "on_month_days": [20]}, False),
        ("set_volume", {"at_time": "00:00"}, False),
    ],
)
def test_only_a_schedule_or_edit_call_at_00_00_sets_midnight(
    name: str, arguments: Mapping[str, object], *, midnight: bool
) -> None:
    call = ToolCall(id="c", name=name, arguments=arguments)
    assert sets_midnight(call) is midnight
    assert midnight_unasked(call, _PARCEL) is midnight
    assert not midnight_unasked(call, "Remind me at midnight to post the parcel.")


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


async def test_a_call_at_00_00_for_a_message_naming_no_midnight_is_refused_once() -> None:
    first = ToolCall(id="c1", name=SCHEDULE_TOOL_NAME, arguments=_ONE_TIME)
    again = ToolCall(id="c2", name=SCHEDULE_TOOL_NAME, arguments={**_ONE_TIME, "text": "again"})
    ran, audit = await _loop(_PARCEL, [first, again])
    assert ran == [{**_ONE_TIME, "text": "again"}]
    refused, kept = audit.records
    assert (refused.ok, refused.detail) == (False, MIDNIGHT_TIME_MSG)
    assert kept.ok


async def test_a_retry_with_the_default_time_runs_after_the_refusal() -> None:
    first = ToolCall(id="c1", name=SCHEDULE_TOOL_NAME, arguments=_ONE_TIME)
    again = ToolCall(id="c2", name=SCHEDULE_TOOL_NAME, arguments=_MORNING)
    ran, audit = await _loop(_PARCEL, [first, again])
    assert ran == [_MORNING]
    assert [record.ok for record in audit.records] == [False, True]


@pytest.mark.parametrize(
    ("query", "arguments"),
    [
        ("Remind me at midnight on 14 December to post the parcel.", _ONE_TIME),
        (_PARCEL, _MORNING),
        ("Remind me at 12 pm on 14 December to post the parcel.", _MORNING),
    ],
)
async def test_a_call_at_a_named_midnight_or_at_another_time_runs_at_once(
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


def test_the_calls_refused_for_00_00_are_read_from_the_tail_by_id() -> None:
    tail = (*_round("c0", _ONE_TIME, MIDNIGHT_TIME_MSG), *_round("c1", _MORNING, "scheduled"))
    record = harness.prepared_slot(tail=tail).snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=_AT
    )
    assert [call.id for call in midnight_refused_calls(record)] == ["c0"]


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
        harness.SESSION, Message(role=Role.USER, text=_PARCEL, at=_AT, turn_id=harness.TURN)
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


async def test_a_deep_retry_at_00_00_runs_when_the_cortex_was_refused_already() -> None:
    ran, audit = await _deep_retry(_round("c0", _ONE_TIME, MIDNIGHT_TIME_MSG), _ONE_TIME)
    assert ran == [_ONE_TIME]
    assert [record.ok for record in audit.records] == [True]


async def test_a_first_deep_call_at_00_00_is_refused() -> None:
    ran, audit = await _deep_retry(_round("c0", _MORNING, "scheduled"), _ONE_TIME)
    assert ran == []
    assert [(record.ok, record.detail) for record in audit.records] == [(False, MIDNIGHT_TIME_MSG)]
