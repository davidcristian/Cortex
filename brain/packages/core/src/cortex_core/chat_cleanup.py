"""A deleted chat's cleanup, and the loop that repeats each one still pending until it succeeds."""

import asyncio
import contextlib
import logging

from cortex_core.errors import MemoryStoreError, ScheduleStoreError, SessionStoreError
from cortex_core.memory_cascade import SessionMemoryCascade
from cortex_core.ports_stores import ScheduleStore, SessionStore

# A pass with nothing pending is one sorted-set read, so a minute costs little and bounds how
# long a chat's memories outlive the return of the store that failed their cleanup.
CLEANUP_REPEAT_INTERVAL_S = 60.0

CLEANUP_ERRORS = (SessionStoreError, MemoryStoreError, ScheduleStoreError)

_logger = logging.getLogger(__name__)


async def finish_cleanup(
    store: SessionStore,
    cascade: SessionMemoryCascade | None,
    schedules: ScheduleStore | None,
    session_id: str,
) -> None:
    """Forget a deleted chat's memories, detach its schedules, then clear its pending record."""
    if cascade is not None:
        await cascade.delete_session_memories(session_id)
    if schedules is not None:
        await schedules.detach_session(session_id)
    await store.clear_cleanup(session_id)


class CleanupRepeater:
    """Finishes every pending cleanup at start and then every ``interval_s`` until ``aclose``."""

    def __init__(
        self,
        store: SessionStore,
        cascade: SessionMemoryCascade | None,
        schedules: ScheduleStore | None,
        *,
        interval_s: float = CLEANUP_REPEAT_INTERVAL_S,
    ) -> None:
        self._store = store
        self._cascade = cascade
        self._schedules = schedules
        self._interval_s = interval_s
        self._stopping = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def repeat(self) -> int:
        """Try each pending cleanup once, oldest first; return how many finished."""
        finished = 0
        for session_id in await self._store.pending_cleanups():
            try:
                await finish_cleanup(self._store, self._cascade, self._schedules, session_id)
            except CLEANUP_ERRORS as err:
                _logger.warning(
                    "a deleted chat's cleanup failed again; the next pass repeats it",
                    extra={"session_id": session_id, "error": str(err)},
                )
            else:
                finished += 1
        if finished:
            _logger.info("finished the pending cleanup of deleted chats", extra={"count": finished})
        return finished

    def start(self) -> None:
        """Run the first pass and the later ones in a task of their own, so boot does not wait."""
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="chat-cleanup")

    async def aclose(self) -> None:
        """Stop the loop and wait out a pass in flight; a repeater never started is a no-op."""
        self._stopping.set()
        if self._task is not None:
            await self._task
            self._task = None

    async def _run(self) -> None:
        while not self._stopping.is_set():
            try:
                await self.repeat()
            except SessionStoreError as err:
                _logger.warning(
                    "the pending chat cleanups could not be read; the next pass reads them again",
                    extra={"error": str(err)},
                )
            except Exception:
                _logger.exception("a chat cleanup pass failed; the next pass tries again")
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._stopping.wait(), timeout=self._interval_s)
