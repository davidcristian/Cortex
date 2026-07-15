"""Parsing the model's calendar-rule vocabulary (ADR-0025): validate, never raise.

Split from ``schedule_args.py`` at the 300-line cap when day-of-month selectors landed
(ADR-0025 monthly addendum), along the responsibility line its siblings already draw: how a
rule's *wall time and dates* are written lives here, while what a creation request or an edit
does with the resulting rule stays with each verb's own parser. Both callers share it, so
``at_time`` means the same thing on ``schedule_task`` and ``edit_scheduled`` by construction.

Same contract as its siblings: a ``str`` return is a correction the model reads back as a
trusted ``is_error`` result, never an exception. The three day selectors are separate named
fields rather than one polymorphic ``on_days`` accepting names, numbers, or dates, because a
small model asked to mix vocabularies in one field will, and a mutual-exclusion correction
teaches the distinction the first time it is hit.

The module also owns how those fields are **advertised** (``day_selector_properties``), not
just how they are read: both verbs used to carry their own copy of the JSON schema, so one
vocabulary had two descriptions that could drift, and a third selector would have made it
three (ADR-0025 yearly addendum). ``at_time`` itself stays with each caller, since its meaning
genuinely differs between them.
"""

import re
from collections.abc import Mapping
from datetime import time
from typing import Any, cast

from cortex_core.schedule_calendar import CalendarRule
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
from cortex_core.schedule_time import DisplayZone, ZoneResolver

BAD_AT_TIME = "'at_time' must be a 24-hour wall-clock time with no seconds, e.g. 09:00"
BAD_IN_ZONE = "'in_zone' must be an IANA timezone name, e.g. America/New_York"
IN_ZONE_NEEDS_AT_TIME = "'in_zone' names the zone of an 'at_time' wall clock; give 'at_time' too"
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


def parse_in_zone(
    arguments: Mapping[str, Any], resolve_zone: ZoneResolver
) -> DisplayZone | None | str:
    """The rule's own timezone from ``in_zone``, ``None`` for the deployment default, or a
    correction string (ADR-0025 per-rule addendum).

    ``None`` when ``in_zone`` is absent, so a rule that names only a time keeps taking the
    deployment zone. A present key is resolved through the injected resolver: an unknown key is a
    correction rather than an enum on the spec, since the IANA set is large and the resolver is
    the authority. Only reached on the ``at_time`` branch; ``in_zone`` without ``at_time`` is
    refused by the caller (``IN_ZONE_NEEDS_AT_TIME``) before this runs.
    """
    raw = arguments.get("in_zone")
    if raw is None:
        return None
    if not isinstance(raw, str):
        return BAD_IN_ZONE
    zone = resolve_zone.resolve(raw)
    if zone is None:
        return f"'in_zone' names no known timezone: {raw!r}; use an IANA key like America/New_York"
    return zone


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
    """The month days named by an ``on_month_days`` list, or a correction string.

    Whole numbers only (a bool is not one, since it subclasses ``int``), each naming a day
    some month contains; a day the *given* month lacks is the selector's business, and it
    clamps rather than refusing (ADR-0025 monthly addendum).
    """
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
    """The calendar dates named by an ``on_dates`` list, or a correction string.

    ``MM-DD`` with no year, since the rule *is* the recurrence: a full ISO date is refused
    rather than truncated, matching ``parse_at_time``'s refusal of a seconds field or an
    offset, because silently dropping the year would answer a question the model did not ask.
    A date no year contains (30 February) is refused by ``MonthDay`` itself, while 29 February
    is accepted and clamps in common years (ADR-0025 yearly addendum).
    """
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


def misplaced_calendar_field(arguments: Mapping[str, Any]) -> str | None:
    """A correction when a calendar-only field is given without ``at_time``, else ``None``.

    ``in_zone`` and the day selectors each describe a wall-clock rule, so each is meaningless
    without the ``at_time`` that anchors one. Shared by creation and edit so the two refuse the
    same misplacement identically; ``in_zone`` is checked first only to give the more specific
    message when both are present.
    """
    if arguments.get("in_zone") is not None:
        return IN_ZONE_NEEDS_AT_TIME
    if has_day_selector(arguments):
        return DAYS_NEED_AT_TIME
    return None


def parse_calendar_rule(
    arguments: Mapping[str, Any], resolve_zone: ZoneResolver
) -> CalendarRule | str:
    """A ``CalendarRule`` from ``at_time`` plus its day selector and optional ``in_zone``, or a
    correction string. Shared by creation and edit so both read one wall-clock vocabulary; each
    caller derives the rule's first occurrence itself, since only it holds the reference instant.
    """
    wall = parse_at_time(arguments.get("at_time"))
    if isinstance(wall, str):
        return wall
    on = parse_day_selector(arguments)
    if isinstance(on, str):
        return on
    zone = parse_in_zone(arguments, resolve_zone)
    if isinstance(zone, str):
        return zone
    hour, minute = wall
    return CalendarRule(hour=hour, minute=minute, on=on, zone=zone)


def parse_day_selector(arguments: Mapping[str, Any]) -> DaySelector | str:
    """The rule's day selector, or a correction string; naming none means every day.

    The three forms are mutually exclusive, refused here rather than left for the rule to
    reconcile: a rule holds exactly one selector, so there is nothing downstream that could
    decide between them.
    """
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


def in_zone_property() -> dict[str, dict[str, Any]]:
    """The ``in_zone`` JSON-schema property, one definition shared by both verbs.

    Kept beside ``day_selector_properties`` and phrased to read on creation and edit alike, so
    the calendar-rule vocabulary has one description the two specs cannot let drift.
    """
    return {
        "in_zone": {
            "type": "string",
            "description": (
                "IANA timezone the 'at_time' wall clock is in, e.g. 'America/New_York'. "
                "Omit to use this schedule's default zone. Only with 'at_time'."
            ),
        },
    }


def day_selector_properties() -> dict[str, dict[str, Any]]:
    """The day-selector JSON-schema properties, one definition shared by both verbs.

    Phrased to read correctly on creation and on an edit alike, which is what lets the two
    specs share them: each says which dates ``at_time`` repeats on, never what ``at_time``
    itself replaces (the part that genuinely differs between the verbs).
    """
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
