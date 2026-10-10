import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime

import pytest

from cortex_core import (
    ConfirmAnswer,
    ConfirmationRequest,
    InMemoryToolRegistry,
    RecordingAuditSink,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
    TurnStamp,
)
from cortex_core.dispatch import CANCELLED_MSG

_AT = datetime(2026, 10, 10, 6, 0, tzinfo=UTC)


class _FixedClock:
    def now(self) -> datetime:
        return _AT


class _NeverAnswers:
    def __init__(self) -> None:
        self.asked = asyncio.Event()

    async def confirm(self, request: ConfirmationRequest) -> ConfirmAnswer:
        del request
        self.asked.set()
        await asyncio.Event().wait()
        return ConfirmAnswer.APPROVED  # pragma: no cover - the wait above never ends


def _spec(name: str) -> ToolSpec:
    return ToolSpec(name=name, description=name, parameters={"type": "object"})


async def _cut(dispatcher: ToolDispatcher, started: asyncio.Event, call: ToolCall) -> None:
    task = asyncio.create_task(dispatcher.dispatch(call, stamp=TurnStamp(turn_id="t1")))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_a_call_cut_while_its_tool_runs_is_audited_as_cancelled() -> None:
    started = asyncio.Event()

    async def slow(arguments: Mapping[str, object]) -> str:
        del arguments
        started.set()
        await asyncio.Event().wait()
        return "never"  # pragma: no cover - the wait above never ends

    sink = RecordingAuditSink()
    registry = InMemoryToolRegistry({"slow": (_spec("slow"), slow)})
    dispatcher = ToolDispatcher(registry, sink, _FixedClock())
    await _cut(dispatcher, started, ToolCall(id="c1", name="slow", arguments={}))
    [line] = sink.records
    assert (line.name, line.ok, line.detail, line.turn_id) == ("slow", False, CANCELLED_MSG, "t1")


async def test_a_call_cut_while_its_confirmation_waits_is_audited_as_cancelled() -> None:
    async def send(arguments: Mapping[str, object]) -> str:
        del arguments
        return "sent"  # pragma: no cover - the call is cut before it runs

    sink = RecordingAuditSink()
    confirmer = _NeverAnswers()
    registry = InMemoryToolRegistry({"send": (_spec("send"), send)})
    dispatcher = ToolDispatcher(registry, sink, _FixedClock(), confirmer=confirmer)
    call = ToolCall(id="c2", name="send", arguments={})
    task = asyncio.create_task(
        dispatcher.dispatch(call, stamp=TurnStamp(turn_id="t2"), confirm_required=True)
    )
    await confirmer.asked.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    [line] = sink.records
    assert (line.name, line.ok, line.detail, line.call_id) == ("send", False, CANCELLED_MSG, "c2")
