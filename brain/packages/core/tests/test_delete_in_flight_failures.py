import asyncio
import logging
from collections.abc import Sequence

import pytest

from cortex_core import (
    EchoInferenceBackend,
    HashEmbedder,
    InMemoryMemoryStore,
    InMemorySessionStore,
    MemoryRecaller,
    MemoryRecord,
    MemoryStoreError,
    SessionStoreError,
    SystemClock,
    TurnCapabilities,
    TurnCompleted,
    TurnEngine,
)

_CHAT = "chat-d"
_UNREMOVED = "the memory row of a chat that may be deleted was not removed"
_UNRECORDED = "memory write unavailable; this exchange was not recorded to memory"


class _UnreadableMark(InMemorySessionStore):
    """Answers the first ``answered`` reads of the deleted set, then raises."""

    def __init__(self, answered: int) -> None:
        super().__init__()
        self._answered = answered
        self.reads = 0

    async def deleted(self, session_id: str) -> bool:
        self.reads += 1
        if self.reads > self._answered:
            msg = "redis is down"
            raise SessionStoreError(msg)
        return await super().deleted(session_id)


class _DeletedOnceStored(InMemoryMemoryStore):
    """Stores the row, then deletes its chat, as a delete that read the chat's rows first does."""

    def __init__(self, sessions: InMemorySessionStore) -> None:
        super().__init__()
        self._sessions = sessions

    async def add(self, record: MemoryRecord, *, recalled: Sequence[str] = ()) -> bool:
        stored = await super().add(record, recalled=recalled)
        await self._sessions.delete(_CHAT)
        return stored


class _FailingDiscard(_DeletedOnceStored):
    async def delete_ids(self, ids: Sequence[str]) -> int:
        del ids
        msg = "connection lost"
        raise MemoryStoreError(msg)


class _FrozenDiscard(_DeletedOnceStored):
    async def delete_ids(self, ids: Sequence[str]) -> int:
        del ids
        await asyncio.Event().wait()
        return 0


async def _turn(
    sessions: InMemorySessionStore,
    memories: InMemoryMemoryStore,
    caplog: pytest.LogCaptureFixture,
    *,
    timeout_s: float = 5.0,
) -> tuple[list[str], logging.LogRecord]:
    caps = TurnCapabilities(
        memory=MemoryRecaller(memories, HashEmbedder(), SystemClock()),
        memory_write_timeout_s=timeout_s,
    )
    engine = TurnEngine(sessions, EchoInferenceBackend(), SystemClock(), capabilities=caps)

    async def run() -> list[object]:
        return [e async for e in engine.handle_turn(_CHAT, "My code is 5813.", turn_id="t-d")]

    with caplog.at_level(logging.ERROR, logger="cortex_core.turn_output"):
        events = await asyncio.wait_for(run(), 5)
    assert isinstance(events[-1], TurnCompleted)
    (record,) = caplog.records
    return [hit.record.id for hit in await memories.search((1.0,) * 16, k=50)], record


async def test_a_failed_discard_keeps_the_row_and_logs_its_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sessions = InMemorySessionStore()
    rows, record = await _turn(sessions, _FailingDiscard(sessions), caplog)
    (row,) = rows
    assert record.message == _UNREMOVED
    assert (record.__dict__["session_id"], record.__dict__["memory_id"]) == (_CHAT, row)
    assert record.exc_info is not None
    assert record.exc_info[0] is MemoryStoreError


async def test_a_frozen_discard_ends_at_the_write_bound(caplog: pytest.LogCaptureFixture) -> None:
    sessions = InMemorySessionStore()
    rows, record = await _turn(sessions, _FrozenDiscard(sessions), caplog, timeout_s=0.05)
    (row,) = rows
    assert (record.message, record.__dict__["memory_id"]) == (_UNREMOVED, row)
    assert record.exc_info is not None
    assert record.exc_info[0] is TimeoutError


async def test_an_unread_mark_after_the_write_keeps_the_row_and_logs_its_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sessions = _UnreadableMark(answered=2)
    rows, record = await _turn(sessions, InMemoryMemoryStore(), caplog)
    (row,) = rows
    assert sessions.reads == 3
    assert (record.message, record.__dict__["memory_id"]) == (_UNREMOVED, row)
    assert record.exc_info is not None
    assert record.exc_info[0] is SessionStoreError


async def test_an_unread_mark_before_the_write_records_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sessions = _UnreadableMark(answered=1)
    rows, record = await _turn(sessions, InMemoryMemoryStore(), caplog)
    assert rows == []
    assert sessions.reads == 2
    assert (record.message, record.__dict__["session_id"]) == (_UNRECORDED, _CHAT)
    assert record.exc_info is not None
    assert record.exc_info[0] is SessionStoreError
