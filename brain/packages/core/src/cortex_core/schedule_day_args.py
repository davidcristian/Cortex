"""Parsing the model's calendar-rule vocabulary (ADR-0025): validate, never raise."""

from collections.abc import Mapping
from datetime import time
from typing import Any, cast

from cortex_core.schedule_calendar import (
    DAILY,
    DAY_NAMES,
    MAX_MONTH_DAY,
    DaySelector,
    MonthDays,
    Weekdays,
)

BAD_AT_TIME = "'at_time' must be a 24-hour wall-clock time with no seconds, e.g. 09:00"
_BAD_ON_DAYS = f"'on_days' must be a non-empty list of weekday names from {', '.join(DAY_NAMES)}"
_BAD_ON_MONTH_DAYS = (
    f"'on_month_days' must be a non-empty list of month days between 1 and {MAX_MONTH_DAY}"
)
_BOTH_SELECTORS = (
    "'at_time' repeats either on weekdays ('on_days') or on days of the month "
    "('on_month_days'), never both"
)
DAYS_NEED_AT_TIME = "'on_days' and 'on_month_days' apply only together with 'at_time'"

# The day-selector arguments, named once so "did the call select days at all?" has one answer.
SELECTOR_KEYS = ("on_days", "on_month_days")


def parse_at_time(value: object) -> tuple[int, int] | str:
    """A bare ``HH:MM`` wall-clock time as ``(hour, minute)``, or a correction string."""
    if not isinstance(value, str):
        return BAD_AT_TIME
    try:
        parsed = time.fromisoformat(value)
    except ValueError:
        return BAD_AT_TIME
    # A rule stores hour and minute only, so accepting finer precision would silently drop
    # part of what the model wrote, and an offset would contradict the zone it is read in.
    if parsed.second or parsed.microsecond or parsed.tzinfo is not None:
        return BAD_AT_TIME
    return parsed.hour, parsed.minute


def parse_on_days(value: object) -> frozenset[int] | str:
    """The weekday numbers named by an ``on_days`` list, or a correction string."""
    if not isinstance(value, list) or not value:
        return _BAD_ON_DAYS
    days: set[int] = set()
    for entry in cast("list[object]", value):
        if not isinstance(entry, str) or entry.lower() not in DAY_NAMES:
            return _BAD_ON_DAYS
        days.add(DAY_NAMES.index(entry.lower()))
    return frozenset(days)


def parse_on_month_days(value: object) -> frozenset[int] | str:
    """The month days named by an ``on_month_days`` list, or a correction string."""
    if not isinstance(value, list) or not value:
        return _BAD_ON_MONTH_DAYS
    days: set[int] = set()
    for entry in cast("list[object]", value):
        if isinstance(entry, bool) or not isinstance(entry, int):
            return _BAD_ON_MONTH_DAYS
        if not 1 <= entry <= MAX_MONTH_DAY:
            return _BAD_ON_MONTH_DAYS
        days.add(entry)
    return frozenset(days)


def has_day_selector(arguments: Mapping[str, Any]) -> bool:
    """Whether the call names any day selector, in either form."""
    return any(arguments.get(key) is not None for key in SELECTOR_KEYS)


def parse_day_selector(arguments: Mapping[str, Any]) -> DaySelector | str:
    """The rule's day selector, or a correction string; naming neither means every day."""
    weekly = arguments.get("on_days")
    monthly = arguments.get("on_month_days")
    if weekly is not None and monthly is not None:
        return _BOTH_SELECTORS
    if monthly is not None:
        month_days = parse_on_month_days(monthly)
        return month_days if isinstance(month_days, str) else MonthDays(days=month_days)
    if weekly is None:
        return DAILY
    weekdays = parse_on_days(weekly)
    return weekdays if isinstance(weekdays, str) else Weekdays(days=weekdays)
