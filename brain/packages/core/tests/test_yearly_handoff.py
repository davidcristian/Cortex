from collections.abc import Mapping
from datetime import UTC, datetime

import pytest
import swap_harness as harness

from cortex_core import (
    SCHEDULE_TOOL_NAME,
    InMemorySessionStore,
    InMemoryToolRegistry,
    Message,
    RecordingAuditSink,
    Role,
    SystemClock,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
    TurnCapabilities,
)
from cortex_core.brain_phase import BrainPhase
from cortex_core.handoff_view import yearly_refused_calls
from cortex_core.schedule_yearly import YEARLY_DATE_MSG

_AT = datetime(2026, 11, 5, 5, 0, 0, tzinfo=UTC)
_BIRTHDAY = "Note that my mother's birthday is on 12 May, and remind me of it the day before."
_MONTHLY = {"at_time": "09:00", "on_month_days": [11]}


def _round(call_id: str, arguments: Mapping[str, object], said: str) -> tuple[Message, Message]:
    call = ToolCall(id=call_id, name=SCHEDULE_TOOL_NAME, arguments=arguments)
    return (
        Message(role=Role.ASSISTANT, text="", at=_AT, turn_id=harness.TURN, tool_calls=(call,)),
        Message(role=Role.TOOL, text=said, at=_AT, turn_id=harness.TURN, tool_call_id=call_id),
    )


def _refused_tail() -> tuple[Message, ...]:
    return (*_round("c0", _MONTHLY, YEARLY_DATE_MSG), *_round("c1", _MONTHLY, "scheduled"))


def test_the_calls_refused_for_a_yearly_date_are_read_from_the_tail_by_id() -> None:
    record = harness.prepared_slot(tail=_refused_tail()).snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=_AT
    )
    assert [call.id for call in yearly_refused_calls(record)] == ["c0"]


async def _deep_retry(retry: Mapping[str, object]) -> tuple[list[object], RecordingAuditSink]:
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
    backend = harness.ScriptedBrainBackend(
        chunks=("done",), tool_calls=(ToolCall(id="c2", name=SCHEDULE_TOOL_NAME, arguments=retry),)
    )
    phase = BrainPhase(
        sessions, backend, SystemClock(), "brain", TurnCapabilities(tools=dispatcher)
    )
    tail = _round("c0", _MONTHLY, YEARLY_DATE_MSG)
    record = harness.prepared_slot(tail=tail).snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=_AT
    )
    events = phase.run(record)
    try:
        _ = [event async for event in events]
    finally:
        await events.aclose()
    return ran, audit


async def test_a_deep_retry_on_the_days_the_cortex_was_refused_runs() -> None:
    ran, audit = await _deep_retry(_MONTHLY)
    assert ran == [_MONTHLY]
    assert [record.ok for record in audit.records] == [True]


@pytest.mark.parametrize("days", [[4], [11, 12]])
async def test_a_deep_monthly_call_on_other_days_is_still_refused(days: list[int]) -> None:
    ran, audit = await _deep_retry({"at_time": "09:00", "on_month_days": days})
    assert ran == []
    assert [(record.ok, record.detail) for record in audit.records] == [(False, YEARLY_DATE_MSG)]
