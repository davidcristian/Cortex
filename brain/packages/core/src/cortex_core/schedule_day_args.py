"""Parsing the model's calendar-rule vocabulary (ADR-0025): validate, never raise."""

import re
from collections.abc import Mapping
from datetime import time
from typing import Any, cast

from cortex_core.schedule_selectors import (
    DAILY,
    DAY_NAMES,
    MAX_MONTH_DAY,
    DaySelector,
    MonthDay,
    MonthDays,
    Weekdays,
    YearDays,
)

BAD_AT_TIME = "'at_time' must be a 24-hour wall-clock time with no seconds, e.g. 09:00"
_BAD_ON_DAYS = f"'on_days' must be a non-empty list of weekday names from {', '.join(DAY_NAMES)}"
_BAD_ON_MONTH_DAYS = (
    f"'on_month_days' must be a non-empty list of month days between 1 and {MAX_MONTH_DAY}"
)
_BAD_ON_DATES = (
    "'on_dates' must be a non-empty list of calendar dates as MM-DD with no year, e.g. "
    '["12-25"] for the 25th of December'
)
_MANY_SELECTORS = (
    "'at_time' repeats on weekdays ('on_days'), on days of the month ('on_month_days'), or "
    "on calendar dates ('on_dates'), never more than one of them"
)
DAYS_NEED_AT_TIME = "'on_days', 'on_month_days', and 'on_dates' apply only together with 'at_time'"

# The day-selector arguments, named once so "did the call select days at all?" has one answer.
SELECTOR_KEYS = ("on_days", "on_month_days", "on_dates")

# ``MM-DD``, one or two digits per part: a leading zero is optional because a small model
# writes "1-5" as readily as "01-05" and neither is ambiguous. A four-digit part fails to
# match, which is what refuses a full ISO date rather than silently dropping its year.
_MONTH_DAY_RE = re.compile(r"^(\d{1,2})-(\d{1,2})$")

_DATE_PATTERN = "^[0-9]{1,2}-[0-9]{1,2}$"


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


def parse_on_dates(value: object) -> frozenset[MonthDay] | str:
    """The calendar dates named by an ``on_dates`` list, or a correction string."""
    if not isinstance(value, list) or not value:
        return _BAD_ON_DATES
    dates: set[MonthDay] = set()
    for entry in cast("list[object]", value):
        if not isinstance(entry, str):
            return _BAD_ON_DATES
        matched = _MONTH_DAY_RE.match(entry)
        if matched is None:
            return _BAD_ON_DATES
        try:
            dates.add(MonthDay(month=int(matched.group(1)), day=int(matched.group(2))))
        except ValueError:
            return _BAD_ON_DATES
    return frozenset(dates)


def has_day_selector(arguments: Mapping[str, Any]) -> bool:
    """Whether the call names any day selector, in any of its forms."""
    return any(arguments.get(key) is not None for key in SELECTOR_KEYS)


def parse_day_selector(arguments: Mapping[str, Any]) -> DaySelector | str:
    """The rule's day selector, or a correction string; naming none means every day."""
    named = [key for key in SELECTOR_KEYS if arguments.get(key) is not None]
    if len(named) > 1:
        return _MANY_SELECTORS
    if not named:
        return DAILY
    key = named[0]
    if key == "on_dates":
        dates = parse_on_dates(arguments[key])
        return dates if isinstance(dates, str) else YearDays(days=dates)
    if key == "on_month_days":
        month_days = parse_on_month_days(arguments[key])
        return month_days if isinstance(month_days, str) else MonthDays(days=month_days)
    weekdays = parse_on_days(arguments[key])
    return weekdays if isinstance(weekdays, str) else Weekdays(days=weekdays)


def day_selector_properties() -> dict[str, dict[str, Any]]:
    """The day-selector JSON-schema properties, one definition shared by both verbs."""
    return {
        "on_days": {
            "type": "array",
            "items": {"type": "string", "enum": list(DAY_NAMES)},
            "description": (
                "Which weekdays 'at_time' repeats on; omit for every day. Only with 'at_time'."
            ),
        },
        "on_month_days": {
            "type": "array",
            "items": {"type": "integer", "minimum": 1, "maximum": MAX_MONTH_DAY},
            "description": (
                "Which days of the month 'at_time' repeats on, e.g. [1] for the 1st of every "
                "month. A day a short month lacks fires on that month's last day, so [31] "
                "means the last day of every month. Only with 'at_time', and never together "
                "with 'on_days' or 'on_dates'."
            ),
        },
        "on_dates": {
            "type": "array",
            "items": {"type": "string", "pattern": _DATE_PATTERN},
            "description": (
                "Which calendar dates 'at_time' repeats on each year, as MM-DD with no year, "
                'e.g. ["12-25"] for every 25th of December. Use this for anniversaries and '
                "renewals rather than a 365 day interval, which drifts on leap years. Only "
                "with 'at_time', and never together with 'on_days' or 'on_month_days'."
            ),
        },
    }
