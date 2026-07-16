"""SeamProgressSink: best-effort, credit-balanced progress onto the Converse queue (ADR-0010).

The sink rides the reply's own buffer credits rather than the confirmer's control path, so a
delegating turn's many steps cannot drift the buffer bound: an emitted event takes a credit that
`events()` releases on dequeue, exactly like a reply delta, and a saturated buffer drops the event
rather than blocking the subagent behind it. (The real wire mapping is `converse`'s and is proven
end to end in test_converse_progress.py; this file's `_to_wire` twin keeps the unit isolated.)
"""

import asyncio

from cortex_core import StatusUpdate, ToolActivity, TurnEvent
from cortex_orchestrator import SeamProgressSink
from cortex_seam import ServerEvent
from cortex_seam import StatusUpdate as WireStatus
from cortex_seam import ToolActivity as WireActivity


def _to_wire(event: TurnEvent) -> ServerEvent:
    """Map the two progress event kinds onto the wire (the sink never emits any other)."""
    if isinstance(event, ToolActivity):
        return ServerEvent(
            tool_activity=WireActivity(tool_name=event.tool_name, summary=event.summary)
        )
    assert isinstance(event, StatusUpdate)
    return ServerEvent(status=WireStatus(state=event.state, detail=event.detail))


def _sink(size: int) -> tuple[SeamProgressSink, list[ServerEvent], asyncio.Semaphore]:
    """A sink over a fresh queue-emit list and its credit semaphore."""
    emitted: list[ServerEvent] = []
    sem = asyncio.Semaphore(size)
    return SeamProgressSink(emitted.append, sem, to_wire=_to_wire), emitted, sem


async def test_emits_a_tool_activity_when_a_credit_is_free() -> None:
    sink, emitted, _ = _sink(2)
    await sink.emit(ToolActivity(tool_name="read", summary="Read a file"))
    (event,) = emitted
    assert event.WhichOneof("event") == "tool_activity"
    assert (event.tool_activity.tool_name, event.tool_activity.summary) == ("read", "Read a file")


async def test_a_status_event_maps_onto_the_wire() -> None:
    sink, emitted, _ = _sink(2)
    await sink.emit(StatusUpdate(state="delegating", detail="delegating 2 subtasks"))
    (event,) = emitted
    assert event.WhichOneof("event") == "status"
    assert (event.status.state, event.status.detail) == ("delegating", "delegating 2 subtasks")


async def test_a_successful_emit_takes_a_buffer_credit() -> None:
    # It rides the data path: the credit it takes is what `events()` releases on dequeue, so the
    # bound stays exact. An unconditional control-path `put` would leave the credit untouched here.
    sink, emitted, sem = _sink(1)
    await sink.emit(ToolActivity(tool_name="read", summary="x"))
    assert len(emitted) == 1
    assert sem.locked()  # the one credit is now taken


async def test_drops_when_no_credit_is_free_instead_of_blocking() -> None:
    # A stalled consumer exhausts the buffer; the sink drops the cosmetic event rather than
    # stalling the subagent behind it. A blocking acquire would hang here (hence the timeout).
    sink, emitted, sem = _sink(1)
    await sem.acquire()  # exhaust the buffer
    async with asyncio.timeout(5.0):
        await sink.emit(ToolActivity(tool_name="read", summary="x"))
    assert emitted == []  # dropped, best-effort
    assert sem.locked()  # and no credit was conjured
