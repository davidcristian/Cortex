"""RpcProgressSink: the real ``ProgressSink`` over one Converse stream's queue."""

import asyncio
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from cortex_core import ProgressEvent, TurnEvent, TurnWaits, Wait, WaitHold
from cortex_seam import ServerEvent


class RpcProgressSink:
    """Emit progress onto the stream's queue, best-effort, and keep the waits of its turn."""

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
        self._waits = TurnWaits(self.emit)

    async def emit(self, event: ProgressEvent) -> None:
        """Queue one progress event if a buffer credit is free right now, else drop it."""
        # Never blocks: ``locked()`` is False only when a permit is free, and no ``await`` sits
        # between that check and the acquire, so the acquire below takes its synchronous path.
        # A saturated buffer drops the event rather than blocking the subagent behind it.
        if self._credits.locked():
            return
        await self._credits.acquire()
        self._emit(self._to_wire(event))

    def hold(self, wait: Wait, *, announce: bool = True) -> AbstractAsyncContextManager[WaitHold]:
        """Hold ``wait`` on this stream's record of what its turn waits on."""
        return self._waits.hold(wait, announce=announce)

    def current(self) -> Wait | None:
        """What this stream's running turn waits on now, for its heartbeat."""
        return self._waits.current()
