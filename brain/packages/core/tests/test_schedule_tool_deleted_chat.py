import logging
from datetime import UTC, datetime

import pytest

from cortex_core import (
    InMemoryScheduleStore,
    InMemorySessionStore,
    ScheduleStoreError,
    ScheduleTaskTool,
    SessionStoreError,
    ToolCall,
    TurnStamp,
)

_NOW = datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)
_ARGS = {"kind": "reminder", "text": "stretch", "in_seconds": 60}


class FixedClock:
    def now(self) -> datetime:
        return _NOW


class DownSessions(InMemorySessionStore):
    async def deleted(self, session_id: str) -> bool:
        del session_id
        msg = "redis down"
        raise SessionStoreError(msg)


class DownDetach(InMemoryScheduleStore):
    async def detach_session(self, session_id: str) -> int:
        del session_id
        msg = "redis down"
        raise ScheduleStoreError(msg)


def _tool(store: InMemoryScheduleStore, sessions: InMemorySessionStore | None) -> ScheduleTaskTool:
    return ScheduleTaskTool(
        store,
        FixedClock(),
        tasks_enabled=False,
        max_active=32,
        item_id_factory=lambda: "item-1",
        sessions=sessions,
    )


def _call(session_id: str, arguments: dict[str, object] | None = None) -> ToolCall:
    stamp = TurnStamp(session_id=session_id, tainted=False)
    return ToolCall(id="c1", name="schedule_task", arguments=arguments or _ARGS, stamp=stamp)


async def _origin(store: InMemoryScheduleStore) -> str:
    item = await store.get("item-1")
    assert item is not None
    return item.session_id


async def test_an_add_in_a_chat_deleted_during_the_call_clears_the_chat() -> None:
    store, sessions = InMemoryScheduleStore(), InMemorySessionStore()
    await sessions.delete("chat-1")
    result = await _tool(store, sessions).invoke(_call("chat-1"))
    assert not result.is_error
    assert result.content.startswith("scheduled reminder item-1")
    assert await _origin(store) == ""


async def test_an_add_in_a_live_chat_keeps_the_chat() -> None:
    store, sessions = InMemoryScheduleStore(), InMemorySessionStore()
    await sessions.delete("chat-2")
    await _tool(store, sessions).invoke(_call("chat-1"))
    assert await _origin(store) == "chat-1"


async def test_without_a_session_store_the_add_keeps_the_chat() -> None:
    store = InMemoryScheduleStore()
    await _tool(store, None).invoke(_call("chat-1"))
    assert await _origin(store) == "chat-1"


async def test_an_add_with_no_chat_reads_no_deleted_mark(caplog: pytest.LogCaptureFixture) -> None:
    store = InMemoryScheduleStore()
    result = await _tool(store, DownSessions()).invoke(_call(""))
    assert not result.is_error
    assert await _origin(store) == ""
    assert caplog.records == []


@pytest.mark.parametrize("down", ["sessions", "detach"])
async def test_a_failed_check_keeps_the_item_and_logs_the_chat(
    down: str, caplog: pytest.LogCaptureFixture
) -> None:
    store = DownDetach() if down == "detach" else InMemoryScheduleStore()
    sessions = DownSessions() if down == "sessions" else InMemorySessionStore()
    await sessions.delete("chat-1")
    with caplog.at_level(logging.ERROR, logger="cortex_core.schedule_tools"):
        result = await _tool(store, sessions).invoke(_call("chat-1"))
    assert not result.is_error
    assert result.content.startswith("scheduled reminder item-1")
    assert await _origin(store) == "chat-1"
    (line,) = caplog.records
    assert line.getMessage() == "a schedule added in a chat that may be deleted kept the chat's id"
    assert line.__dict__["session_id"] == "chat-1"


async def test_a_held_duplicate_adds_nothing_to_clear() -> None:
    store, sessions = InMemoryScheduleStore(), InMemorySessionStore()
    tool = _tool(store, sessions)
    await tool.invoke(_call("chat-1"))
    await sessions.delete("chat-1")
    again = await tool.invoke(_call("chat-1"))
    assert "no copy was added" in again.content
    assert await _origin(store) == "chat-1"
