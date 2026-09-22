"""The wait one delegated batch reports: how many of its subtasks queue and how many run."""

from cortex_core.waits import DELEGATING, QUEUED, Wait, WaitHold


def _subtasks(count: int) -> str:
    """``count`` subtasks, in words."""
    return f"{count} subtask{'' if count == 1 else 's'}"


def batch_wait(queued: int, running: int) -> Wait:
    """``queued`` while any subtask waits for room, else ``delegating``, with both counts."""
    if queued and running:
        return Wait(QUEUED, f"{_subtasks(running)} running, {queued} waiting for room to run")
    if queued:
        return Wait(QUEUED, f"{_subtasks(queued)} waiting for room to run")
    return Wait(DELEGATING, f"{_subtasks(running)} running")


class DelegationBoard:
    """Counts one batch's subtasks as they are admitted and end, restating the batch's hold."""

    def __init__(self, hold: WaitHold, count: int) -> None:
        self._hold = hold
        self._queued = count
        self._running = 0

    def subtask(self) -> "BoardedSubtask":
        """One subtask of the batch, counted as queued until it is admitted."""
        return BoardedSubtask(self)

    async def move(self, *, queued: int, running: int) -> None:
        """Apply one subtask's change of counts and restate the batch's wait."""
        self._queued += queued
        self._running += running
        if self._queued or self._running:
            await self._hold.restate(batch_wait(self._queued, self._running))


class BoardedSubtask:
    """One subtask's place on a ``DelegationBoard``: queued, then running, then gone."""

    def __init__(self, board: DelegationBoard) -> None:
        self._board = board
        self._running = False

    async def admitted(self) -> None:
        """The subtask was admitted and now runs."""
        self._running = True
        await self._board.move(queued=-1, running=1)

    async def ended(self) -> None:
        """The subtask ended, admitted or not."""
        if self._running:
            await self._board.move(queued=0, running=-1)
        else:
            await self._board.move(queued=-1, running=0)
