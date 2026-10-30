import asyncio
import logging
from collections.abc import Sequence
from datetime import UTC, datetime

import pytest

from cortex_core import (
    CleanupRepeater,
    InMemoryMemoryStore,
    InMemoryScheduleStore,
    InMemorySessionStore,
    MemoryRecord,
    MemoryStoreError,
    ScheduledItem,
    ScheduleKind,
    ScheduleStoreError,
    SessionMemoryCascade,
    SessionMemoryScope,
    SessionStoreError,
    finish_cleanup,
)

_LOGGER = "cortex_core.chat_cleanup"
_AT = datetime(2026, 10, 30, 1, 0, tzinfo=UTC)


class _FailingFor(InMemoryMemoryStore):
    def __init__(self, failing: set[str]) -> None:
        super().__init__()
        self.failing = failing

    async def delete_written_by(self, session_id: str) -> int:
        if session_id in self.failing:
            msg = "pgvector is down"
            raise MemoryStoreError(msg)
        return await super().delete_written_by(session_id)


class _DownDetach(InMemoryScheduleStore):
    async def detach_session(self, session_id: str) -> int:
        del session_id
        msg = "redis is down"
        raise ScheduleStoreError(msg)


class _CountedPasses(InMemorySessionStore):
    def __init__(self, failure: Exception | None = None) -> None:
        super().__init__()
        self.passes = 0
        self.second_pass = asyncio.Event()
        self._failure = failure

    async def pending_cleanups(self) -> Sequence[str]:
        self.passes += 1
        if self.passes >= 2:
            self.second_pass.set()
        if self._failure is not None:
            raise self._failure
        return await super().pending_cleanups()


def _memory(session_id: str) -> MemoryRecord:
    return MemoryRecord(
        id=f"m-{session_id}",
        text="a secret",
        embedding=(1.0,),
        scope=session_id,
        at=_AT,
        session_id=session_id,
    )


def _reminder(session_id: str) -> ScheduledItem:
    return ScheduledItem(
        id=f"r-{session_id}",
        kind=ScheduleKind.REMINDER,
        text="stretch",
        session_id=session_id,
        due_at=_AT,
        created_at=_AT,
    )


async def _deleted(store: InMemorySessionStore, *session_ids: str) -> None:
    for session_id in session_ids:
        await store.delete(session_id)


async def test_finishing_a_cleanup_forgets_detaches_then_clears_the_record() -> None:
    sessions, memories, schedules = (
        InMemorySessionStore(),
        InMemoryMemoryStore(),
        InMemoryScheduleStore(),
    )
    await memories.add(_memory("gone"))
    await schedules.add(_reminder("gone"))
    await _deleted(sessions, "gone")

    await finish_cleanup(
        sessions, SessionMemoryCascade(memories, SessionMemoryScope()), schedules, "gone"
    )

    assert list(await memories.search((1.0,), k=5, scopes=["gone"])) == []
    detached = await schedules.get("r-gone")
    assert detached is not None
    assert detached.session_id == ""
    assert list(await sessions.pending_cleanups()) == []


async def test_finishing_a_cleanup_with_memory_and_schedules_off_only_clears_it() -> None:
    sessions = InMemorySessionStore()
    await _deleted(sessions, "gone")
    await finish_cleanup(sessions, None, None, "gone")
    assert list(await sessions.pending_cleanups()) == []


@pytest.mark.parametrize("step", ["cascade", "detach"])
async def test_a_failed_step_leaves_the_record_pending(step: str) -> None:
    sessions = InMemorySessionStore()
    await _deleted(sessions, "gone")
    failing = {"gone"} if step == "cascade" else set[str]()
    cascade = SessionMemoryCascade(_FailingFor(failing), SessionMemoryScope())
    schedules = _DownDetach() if step == "detach" else InMemoryScheduleStore()
    with pytest.raises((MemoryStoreError, ScheduleStoreError)):
        await finish_cleanup(sessions, cascade, schedules, "gone")
    assert list(await sessions.pending_cleanups()) == ["gone"]


async def test_a_pass_finishes_each_pending_cleanup_and_repeats_only_a_failed_one(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sessions, memories = InMemorySessionStore(), _FailingFor({"stuck"})
    for session_id in ("first", "stuck", "last"):
        await memories.add(_memory(session_id))
    await _deleted(sessions, "first", "stuck", "last")
    repeater = CleanupRepeater(sessions, SessionMemoryCascade(memories, SessionMemoryScope()), None)

    with caplog.at_level(logging.INFO, logger=_LOGGER):
        assert await repeater.repeat() == 2

    assert list(await sessions.pending_cleanups()) == ["stuck"]
    assert [hit.record.id for hit in await memories.search((1.0,), k=5)] == ["m-stuck"]
    warned, finished = caplog.records
    assert warned.getMessage() == "a deleted chat's cleanup failed again; the next pass repeats it"
    assert warned.__dict__["session_id"] == "stuck"
    assert warned.__dict__["error"] == "pgvector is down"
    assert finished.getMessage() == "finished the pending cleanup of deleted chats"
    assert finished.__dict__["count"] == 2

    memories.failing.clear()
    assert await repeater.repeat() == 1
    assert list(await sessions.pending_cleanups()) == []


async def test_a_pass_with_nothing_pending_finishes_nothing_and_logs_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        assert await CleanupRepeater(InMemorySessionStore(), None, None).repeat() == 0
    assert caplog.records == []


async def test_start_runs_a_pass_at_once_then_one_per_interval_until_closed() -> None:
    sessions = _CountedPasses()
    await _deleted(sessions, "gone")
    repeater = CleanupRepeater(sessions, None, None, interval_s=0.01)

    repeater.start()
    repeater.start()
    await asyncio.wait_for(sessions.second_pass.wait(), timeout=5)
    await repeater.aclose()
    passes = sessions.passes
    await asyncio.sleep(0.05)

    assert list(await sessions.pending_cleanups()) == []
    assert sessions.passes == passes + 1


async def test_the_first_pass_does_not_wait_for_the_interval() -> None:
    sessions = _CountedPasses()
    await _deleted(sessions, "gone")
    repeater = CleanupRepeater(sessions, None, None, interval_s=3600)
    repeater.start()
    for _ in range(100):
        if sessions.passes:
            break
        await asyncio.sleep(0.01)
    before_close = sessions.passes
    await repeater.aclose()
    assert before_close == 1
    assert list(await sessions.pending_cleanups()) == []


async def test_closing_a_repeater_never_started_does_nothing() -> None:
    await CleanupRepeater(InMemorySessionStore(), None, None).aclose()


@pytest.mark.parametrize(
    ("failure", "level", "message"),
    [
        (
            SessionStoreError("redis is down"),
            logging.WARNING,
            "the pending chat cleanups could not be read; the next pass reads them again",
        ),
        (
            RuntimeError("a defect"),
            logging.ERROR,
            "a chat cleanup pass failed; the next pass tries again",
        ),
    ],
)
async def test_the_loop_outlives_a_pass_that_raises(
    failure: Exception, level: int, message: str, caplog: pytest.LogCaptureFixture
) -> None:
    sessions = _CountedPasses(failure)
    repeater = CleanupRepeater(sessions, None, None, interval_s=0.01)
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        repeater.start()
        await asyncio.wait_for(sessions.second_pass.wait(), timeout=5)
        await repeater.aclose()
    assert sessions.passes >= 2
    assert {(r.levelno, r.getMessage()) for r in caplog.records} == {(level, message)}
