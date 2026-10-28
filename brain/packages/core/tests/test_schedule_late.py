from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from cortex_core import (
    LATE_FIRE_FLOOR,
    UTC_DISPLAY,
    CalendarRule,
    DisplayZone,
    ScheduledItem,
    ScheduleKind,
    late_phrase,
)

_DUE = datetime(2026, 10, 26, 7, 0, 0, tzinfo=UTC)
_BERLIN = DisplayZone(name="Europe/Berlin", tz=ZoneInfo("Europe/Berlin"))
_POLL = timedelta(seconds=5)


def _item(rule: CalendarRule | None = None) -> ScheduledItem:
    return ScheduledItem(
        id="r1",
        kind=ScheduleKind.REMINDER,
        text="check the oven",
        session_id="",
        due_at=_DUE,
        created_at=_DUE - timedelta(hours=1),
        rule=rule,
    )


@pytest.mark.parametrize("delay", [timedelta(0), timedelta(seconds=7), LATE_FIRE_FLOOR])
def test_a_fire_within_the_floor_is_on_time(delay: timedelta) -> None:
    assert late_phrase(_item(), _DUE + delay, _BERLIN, _POLL) == ""


def test_a_fire_past_the_floor_names_its_due_time_in_the_zone() -> None:
    fired = _DUE + LATE_FIRE_FLOOR + timedelta(seconds=1)
    assert late_phrase(_item(), fired, _BERLIN, _POLL) == ", due 08:00"


def test_a_late_fire_on_a_later_day_names_the_day() -> None:
    assert late_phrase(_item(), _DUE + timedelta(days=1), UTC_DISPLAY, _POLL) == (
        ", due 07:00 yesterday"
    )
    assert late_phrase(_item(), _DUE + timedelta(days=3), UTC_DISPLAY, _POLL) == (
        ", due 07:00 3 days ago"
    )


def test_a_long_poll_widens_the_margin_to_two_polls() -> None:
    poll = timedelta(minutes=2)
    assert late_phrase(_item(), _DUE + timedelta(minutes=4), _BERLIN, poll) == ""
    assert late_phrase(_item(), _DUE + timedelta(minutes=4, seconds=1), _BERLIN, poll) == (
        ", due 08:00"
    )


def test_a_calendar_rule_zone_overrides_the_default() -> None:
    tokyo = DisplayZone(name="Asia/Tokyo", tz=ZoneInfo("Asia/Tokyo"))
    item = _item(CalendarRule(hour=16, minute=0, zone=tokyo))
    assert late_phrase(item, _DUE + timedelta(hours=2), _BERLIN, _POLL) == ", due 16:00"


def test_a_long_run_that_started_on_time_is_not_late() -> None:
    started = _DUE + timedelta(seconds=3)
    fired = _DUE + timedelta(minutes=40)
    assert late_phrase(_item(), fired, _BERLIN, _POLL, started_at=started) == ""


def test_a_late_start_is_named_with_the_day_counted_from_the_fire() -> None:
    started = _DUE + timedelta(hours=16, minutes=50)
    fired = started + timedelta(minutes=20)
    assert late_phrase(_item(), started, UTC_DISPLAY, _POLL) == ", due 07:00"
    assert late_phrase(_item(), fired, UTC_DISPLAY, _POLL, started_at=started) == (
        ", due 07:00 yesterday"
    )
