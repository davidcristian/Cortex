from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from cortex_core import (
    UTC_DISPLAY,
    DisplayZone,
    InMemoryScheduleStore,
    ScheduleTaskTool,
    ToolCall,
    TurnStamp,
    ZoneContext,
    next_occurrence,
)

_NOW = datetime(2026, 11, 5, 5, 0, tzinfo=UTC)
_LOS_ANGELES = DisplayZone(name="America/Los_Angeles", tz=ZoneInfo("America/Los_Angeles"))


class _FixedClock:
    def now(self) -> datetime:
        return _NOW


class _MapResolver:
    def resolve(self, name: str) -> DisplayZone | None:
        return _LOS_ANGELES if name == _LOS_ANGELES.name else None


def _tool() -> tuple[ScheduleTaskTool, InMemoryScheduleStore]:
    store = InMemoryScheduleStore()
    tool = ScheduleTaskTool(
        store,
        _FixedClock(),
        tasks_enabled=False,
        max_active=32,
        zones=ZoneContext(resolver=_MapResolver()),
        item_id_factory=lambda: "item-1",
    )
    return tool, store


async def _schedule(**arguments: object) -> tuple[str, bool, InMemoryScheduleStore]:
    tool, store = _tool()
    call = ToolCall(
        id="c1",
        name="schedule_task",
        arguments={"kind": "reminder", "text": "pay the gas bill", **arguments},
        stamp=TurnStamp(session_id="s1"),
    )
    result = await tool.invoke(call)
    return result.content, result.is_error, store


async def _first_due(**arguments: object) -> datetime:
    content, is_error, store = await _schedule(**arguments)
    assert not is_error, content
    (item,) = await store.list_active()
    return item.due_at


async def test_a_monthly_repeat_starts_on_the_first_selected_day_on_or_after_the_start() -> None:
    due = await _first_due(at_time="09:00", on_month_days=[15], starting="2027-06-15")
    assert due == datetime(2027, 6, 15, 9, 0, tzinfo=UTC)


async def test_a_start_between_selected_days_moves_to_the_next_one() -> None:
    due = await _first_due(at_time="09:00", on_month_days=[1], starting="2027-05-02")
    assert due == datetime(2027, 6, 1, 9, 0, tzinfo=UTC)


async def test_an_occurrence_at_midnight_on_the_start_day_is_kept() -> None:
    due = await _first_due(at_time="00:00", on_month_days=[15], starting="2027-06-15")
    assert due == datetime(2027, 6, 15, 0, 0, tzinfo=UTC)


async def test_a_start_of_today_never_schedules_a_time_already_past() -> None:
    due = await _first_due(at_time="04:00", starting="2026-11-05")
    assert due == datetime(2026, 11, 6, 4, 0, tzinfo=UTC)


async def test_the_next_occurrence_after_the_first_fire_follows_the_rule() -> None:
    _, _, store = await _schedule(at_time="09:00", on_month_days=[15], starting="2027-06-15")
    (item,) = await store.list_active()
    after = next_occurrence(item, item.due_at, UTC_DISPLAY)
    assert after == datetime(2027, 7, 15, 9, 0, tzinfo=UTC)


async def test_the_start_day_is_read_in_the_rule_zone() -> None:
    due = await _first_due(at_time="22:00", in_zone=_LOS_ANGELES.name, starting="2026-11-04")
    assert due == datetime(2026, 11, 5, 6, 0, tzinfo=UTC)


async def test_a_future_start_begins_at_midnight_in_the_rule_zone() -> None:
    due = await _first_due(at_time="20:00", in_zone=_LOS_ANGELES.name, starting="2026-11-06")
    assert due == datetime(2026, 11, 7, 4, 0, tzinfo=UTC)


async def test_a_start_before_today_is_refused_and_names_today() -> None:
    content, is_error, store = await _schedule(
        at_time="09:00", on_month_days=[1], starting="2026-05-01"
    )
    assert is_error
    assert "'starting' 2026-05-01 has already passed; today is 2026-11-05 (UTC)" in content
    assert await store.list_active() == ()


@pytest.mark.parametrize("starting", [20270615, "15 June", "2027-06-15T09:00:00", ""])
async def test_a_start_that_is_not_a_date_is_refused(starting: object) -> None:
    content, is_error, store = await _schedule(at_time="09:00", starting=starting)
    assert is_error
    assert "'starting' must be an ISO-8601 calendar date" in content
    assert await store.list_active() == ()


@pytest.mark.parametrize(
    "timing", [{"at": "2027-03-03T09:00:00", "every_seconds": 2_419_200}, {"in_seconds": 60}]
)
async def test_a_start_without_at_time_is_refused(timing: dict[str, Any]) -> None:
    content, is_error, store = await _schedule(starting="2027-03-03", **timing)
    assert is_error
    assert "'starting' sets the first day of an 'at_time' repeat" in content
    assert await store.list_active() == ()


async def test_a_start_with_no_later_occurrence_is_unschedulable() -> None:
    content, is_error, _ = await _schedule(
        at_time="09:00", on_month_days=[15], starting="9999-12-30"
    )
    assert is_error
    assert "has no next occurrence" in content


def test_the_spec_offers_the_start_day() -> None:
    tool, _ = _tool()
    starting = tool.spec.parameters["properties"]["starting"]
    assert starting["type"] == "string"
    assert "first day the rule selects on or after it" in starting["description"]
    assert "'starting' (its first day)" in tool.spec.description
