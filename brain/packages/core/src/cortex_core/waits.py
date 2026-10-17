"""What a running turn waits on: the seven keys, one wait, and the record of open waits."""

from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass

from cortex_core.events import StatusUpdate

THINKING = "thinking"
QUEUED = "queued"
DELEGATING = "delegating"
SWAPPING = "swapping"
FOLDING = "folding"
CALLING = "calling"
ASKING = "asking"

WAIT_KEYS = (THINKING, QUEUED, DELEGATING, SWAPPING, FOLDING, CALLING, ASKING)

THINKING_DETAIL = "working out the reply"
CALLING_DETAIL = "waiting for a tool to finish"
ASKING_DETAIL = "waiting for you to approve or decline the action"


@dataclass(frozen=True, slots=True)
class Wait:
    """One thing a turn waits on: a key from ``WAIT_KEYS`` and the sentence the overlay shows."""

    key: str
    detail: str


GENERATING = Wait(THINKING, THINKING_DETAIL)
TOOL_RUNNING = Wait(CALLING, CALLING_DETAIL)
USER_ASKED = Wait(ASKING, ASKING_DETAIL)


CLEARED = StatusUpdate(state="", detail="")


class WaitHold:
    """One open wait on a ``TurnWaits`` record, which its holder may restate while it is open."""

    def __init__(self, record: "TurnWaits", wait: Wait, *, announced: bool) -> None:
        self._record = record
        self.wait = wait
        self.announced = announced

    async def restate(self, wait: Wait, *, announce: bool = True) -> None:
        """Replace this hold's wait, announcing it when it is the innermost one."""
        before, sent = self._record.current(), self._record.sent()
        self.wait = wait
        self.announced = announce
        await self._record.changed(before, sent, announce=announce)


class TurnWaits:
    """The waits a turn has open, innermost last; the innermost one is what the turn waits on."""

    def __init__(self, emit: Callable[[StatusUpdate], Awaitable[None]]) -> None:
        self._emit = emit
        self._open: list[WaitHold] = []

    def current(self) -> Wait | None:
        """The most recently opened wait still open, or ``None`` when none is."""
        return self._open[-1].wait if self._open else None

    def sent(self) -> Wait | None:
        """The innermost wait when this record sends it as a status, else ``None``."""
        if not self._open or not self._open[-1].announced:
            return None
        wait = self._open[-1].wait
        return None if wait.key == THINKING else wait

    @asynccontextmanager
    async def hold(self, wait: Wait, *, announce: bool = True) -> AsyncGenerator[WaitHold, None]:
        """Keep ``wait`` open for the block; ``announce`` is false when the holder reports it."""
        before, sent = self.current(), self.sent()
        held = WaitHold(self, wait, announced=announce)
        self._open.append(held)
        try:
            await self.changed(before, sent, announce=announce)
            yield held
        finally:
            before, sent = self.current(), self.sent()
            self._open.remove(held)
            await self.changed(before, sent, announce=True)

    async def changed(self, before: Wait | None, sent: Wait | None, *, announce: bool) -> None:
        """Send the innermost wait when it changed, or a clear when it is no longer one sent.

        ``before`` and ``sent`` are ``current()`` and ``sent()`` from just before the change.
        """
        # A ``thinking`` status is one piece of the model's reasoning, which the overlay adds to
        # the reply's trace, so a thinking wait reaches the body only in a heartbeat.
        if not announce:
            return
        now = self.current()
        if now is not None and now.key != THINKING:
            if now != before:
                await self._emit(StatusUpdate(state=now.key, detail=now.detail))
        elif sent is not None:
            await self._emit(CLEARED)
