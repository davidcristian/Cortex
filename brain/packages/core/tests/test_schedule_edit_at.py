from datetime import UTC, datetime

import pytest

from cortex_core import (
    EditScheduledTool,
    InMemoryScheduleStore,
    ScheduledItem,
    ScheduleStoreError,
    ScheduleTaskTool,
    ToolCall,
    TurnStamp,
)
from cortex_core.schedule_edit_at import AT_ALONE, at_repeats

_NOW = datetime(2026, 11, 8, 8, 0, tzinfo=UTC)


class _FixedClock:
    def now(self) -> datetime:
        return _NOW


class _DownStore(InMemoryScheduleStore):
    async def get(self, item_id: str) -> ScheduledItem | None:
        msg = f"redis is down while reading {item_id}"
        raise ScheduleStoreError(msg)


class _RacedStore(InMemoryScheduleStore):
    async def snooze(self, item_id: str, *, until: datetime) -> bool:
        del item_id, until
        return False


def _call(name: str, arguments: dict[str, object]) -> ToolCall:
    return ToolCall(id="c1", name=name, arguments=arguments, stamp=TurnStamp(session_id="s1"))


async def _stored(store: InMemoryScheduleStore, **timing: object) -> None:
    tool = ScheduleTaskTool(
        store, _FixedClock(), tasks_enabled=False, max_active=32, item_id_factory=lambda: "item-1"
    )
    arguments: dict[str, object] = {"kind": "reminder", "text": "send the parcel", **timing}
    result = await tool.invoke(_call("schedule_task", arguments))
    assert not result.is_error, result.content


async def _edit(store: InMemoryScheduleStore, **changes: object) -> tuple[str, bool]:
    tool = EditScheduledTool(store, _FixedClock())
    result = await tool.invoke(_call("edit_scheduled", {"id": "item-1", **changes}))
    return result.content, result.is_error


async def test_at_moves_a_one_time_item_and_keeps_it_one_time() -> None:
    store = InMemoryScheduleStore()
    await _stored(store, at="2026-12-14T09:00:00")
    content, is_error = await _edit(store, at="2026-12-14T15:00:00")
    assert (content, is_error) == ("edited item-1: now due 2026-12-14T15:00:00+00:00", False)
    (item,) = await store.list_active()
    assert (item.due_at, item.rule, item.every) == (
        datetime(2026, 12, 14, 15, tzinfo=UTC),
        None,
        None,
    )


async def test_at_with_new_text_changes_both() -> None:
    store = InMemoryScheduleStore()
    await _stored(store, at="2026-11-10T09:00:00")
    _, is_error = await _edit(store, at="2026-11-11T09:00:00", text="call mom")
    (item,) = await store.list_active()
    assert (is_error, item.text, item.due_at) == (
        False,
        "call mom",
        datetime(2026, 11, 11, 9, tzinfo=UTC),
    )


@pytest.mark.parametrize(
    ("changes", "said"),
    [
        ({"at": "2026-11-11T09:00:00", "at_time": "09:00"}, AT_ALONE),
        ({"at": "2026-11-11T09:00:00", "on_days": ["wed"]}, AT_ALONE),
        ({"at": "2026-11-11T09:00:00", "every_seconds": 0}, AT_ALONE),
        ({"at": "2026-11-11T09:00:00", "text": "  "}, "'text' must be a non-empty string"),
        ({"at": "Wednesday"}, "'at' must be an ISO-8601 date-time, e.g. 2026-07-12T18:00:00"),
    ],
)
async def test_a_bad_move_is_corrected_and_changes_nothing(
    changes: dict[str, object], said: str
) -> None:
    store = InMemoryScheduleStore()
    await _stored(store, at="2026-11-10T09:00:00")
    assert await _edit(store, **changes) == (said, True)
    (item,) = await store.list_active()
    assert (item.text, item.due_at) == ("send the parcel", datetime(2026, 11, 10, 9, tzinfo=UTC))


async def test_a_past_at_is_corrected() -> None:
    store = InMemoryScheduleStore()
    await _stored(store, at="2026-11-10T09:00:00")
    content, is_error = await _edit(store, at="2026-11-01T09:00:00")
    assert is_error
    assert content.startswith("'at' 2026-11-01T09:00:00+00:00 has already passed")


async def test_at_on_a_repeating_item_is_corrected() -> None:
    store = InMemoryScheduleStore()
    await _stored(store, at_time="09:00")
    assert await _edit(store, at="2026-11-11T09:00:00") == (at_repeats("item-1"), True)


@pytest.mark.parametrize(
    ("store", "said"),
    [
        (InMemoryScheduleStore(), "no scheduled item item-1"),
        (_DownStore(), "the schedule store is unavailable: redis is down while reading item-1"),
    ],
)
async def test_a_missing_item_or_a_down_store_is_reported(
    store: InMemoryScheduleStore, said: str
) -> None:
    assert await _edit(store, at="2026-11-11T09:00:00") == (said, True)


async def test_a_move_raced_by_a_fire_is_reported() -> None:
    store = _RacedStore()
    await _stored(store, at="2026-11-10T09:00:00")
    content, is_error = await _edit(store, at="2026-11-11T09:00:00")
    assert (content, is_error) == (
        "item-1 changed underneath (fired or cancelled); use list_scheduled to re-check",
        True,
    )
