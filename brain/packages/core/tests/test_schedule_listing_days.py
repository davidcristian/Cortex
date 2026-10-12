from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from cortex_core import (
    CalendarRule,
    DisplayZone,
    InMemoryScheduleStore,
    ListScheduledTool,
    ScheduledItem,
    ScheduleKind,
    ToolCall,
)

_NOW = datetime(2026, 7, 12, 22, 30, 0, tzinfo=UTC)
_BUCHAREST = DisplayZone(name="Europe/Bucharest", tz=ZoneInfo("Europe/Bucharest"))
_NEW_YORK = DisplayZone(name="America/New_York", tz=ZoneInfo("America/New_York"))


class _Clock:
    def now(self) -> datetime:
        return _NOW


def _item(due_at: datetime, rule: CalendarRule | None = None) -> ScheduledItem:
    return ScheduledItem(
        id="item-1",
        kind=ScheduleKind.REMINDER,
        text="call Ana",
        session_id="s",
        due_at=due_at,
        created_at=_NOW,
        rule=rule,
    )


async def _lines(item: ScheduledItem, zone: DisplayZone | None = None) -> list[str]:
    store = InMemoryScheduleStore()
    await store.add(item)
    tool = (
        ListScheduledTool(store, _Clock())
        if zone is None
        else ListScheduledTool(store, _Clock(), zone=zone)
    )
    result = await tool.invoke(ToolCall(id="l", name="list_scheduled", arguments={}))
    return result.content.splitlines()


async def test_the_listing_opens_with_the_current_date_time() -> None:
    lines = await _lines(_item(_NOW + timedelta(hours=1)))
    assert lines[0] == "The current date-time is 2026-07-12T22:30:00+00:00 (UTC)."
    assert len(lines) == 2


@pytest.mark.parametrize(
    ("due_at", "day"),
    [
        (datetime(2026, 7, 12, 23, 59, tzinfo=UTC), "today"),
        (datetime(2026, 7, 13, 0, 0, tzinfo=UTC), "tomorrow"),
        (datetime(2026, 7, 14, 9, 0, tzinfo=UTC), "in 2 days"),
        (datetime(2026, 7, 22, 9, 0, tzinfo=UTC), "in 10 days"),
        (datetime(2026, 7, 11, 23, 59, tzinfo=UTC), "yesterday"),
        (datetime(2026, 7, 10, 9, 0, tzinfo=UTC), "2 days ago"),
    ],
)
async def test_each_due_time_names_its_day_counted_from_today(due_at: datetime, day: str) -> None:
    lines = await _lines(_item(due_at))
    assert lines[1] == f"[item-1] reminder due {due_at.isoformat()} ({day}): call Ana"


async def test_the_day_is_counted_in_the_display_zone() -> None:
    lines = await _lines(_item(datetime(2026, 7, 13, 5, 0, tzinfo=UTC)), _BUCHAREST)
    assert lines[0] == "The current date-time is 2026-07-13T01:30:00+03:00 (Europe/Bucharest)."
    assert "due 2026-07-13T08:00:00+03:00 (today): call Ana" in lines[1]


async def test_the_day_is_counted_in_the_items_own_zone() -> None:
    rule = CalendarRule(hour=1, minute=0, zone=_NEW_YORK)
    item = _item(datetime(2026, 7, 13, 5, 0, tzinfo=UTC), rule)
    lines = await _lines(item, _BUCHAREST)
    assert "due 2026-07-13T01:00:00-04:00 (tomorrow), every day at 01:00" in lines[1]
