"""SeamProgressSink: the real ``ProgressSink`` over one Converse stream's queue (ADR-0010).

One instance per ``_ConverseStream``, bound to that stream's output queue and its credit
semaphore. It is the side channel a spawned subagent surfaces its progress onto while the turn
task is suspended inside ``dispatch`` and its own generator cannot yield: the batch's scale (a
``StatusUpdate``) and each subagent's audited tool steps (a ``ToolActivity``), mapped onto the
wire by the same ``_to_server_event`` the turn's own events use (injected, so this module never
imports ``converse``).

Unlike the confirmer, which must always deliver its request, progress is **best-effort and
credit-balanced**: ``emit`` takes a buffer credit only when one is free right now (the same
``max_buffered_events`` bound the reply's deltas draw on), else it drops the event. So a stalled
consumer loses cosmetic progress rather than stalling the subagent behind it, and the buffer bound
does not drift the way an unconditional control-path ``put`` would: an acquired-then-dequeued
progress event balances exactly like a reply delta (``events`` releases one credit per dequeue),
whereas the confirmer's control-path events over-credit by design (bounded, ADR-0022). Nothing is
persisted and nothing survives the turn, so the one hard rule holds by the sink carrying no state.

While a subagent runs, the turn task is suspended inside ``dispatch`` and is *not* itself
acquiring credits, so the sink contends with no producer for them and the ordering on the queue is
the natural one: the spawn call's own ``ToolActivity`` (already queued by the turn before it
suspended), then the batch status and the subagents' steps, then the reply resumes.
"""

import asyncio
from collections.abc import Callable

from cortex_core import ProgressEvent, TurnEvent
from cortex_seam import ServerEvent


class SeamProgressSink:
    """Emit a subagent's progress onto the stream's queue, best-effort and credit-balanced."""

    def __init__(
        self,
        emit: Callable[[ServerEvent], None],
        credit_sem: asyncio.Semaphore,
        *,
        to_wire: Callable[[TurnEvent], ServerEvent],
    ) -> None:
        self._emit = emit
        self._credits = credit_sem
        self._to_wire = to_wire

    async def emit(self, event: ProgressEvent) -> None:
        """Queue one progress event if a buffer credit is free right now, else drop it.

        Non-blocking: ``locked()`` is False only when a permit is free (and no waiter is owed it),
        and no ``await`` sits between that check and the acquire, so in single-threaded asyncio the
        permit is still ours when ``acquire`` takes its synchronous fast path (no suspension). A
        saturated buffer (``locked()``) drops the event rather than blocking the subagent, and the
        turn's own deltas keep their exact bound.
        """
        if self._credits.locked():
            return
        await self._credits.acquire()
        self._emit(self._to_wire(event))
