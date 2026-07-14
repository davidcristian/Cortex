"""Calendar recurrence: a wall-clock rule and the zone-aware occurrence math (ADR-0025).

The second recurrence *shape*, beside ``ScheduledItem.every``. An interval is the wrong tool
for "every weekday at 09:00": ``every`` is a ``timedelta`` while a calendar day is 23, 24, or
25 hours long depending on daylight saving, so a fixed interval drifts off the wall clock
exactly when a user notices. A ``CalendarRule`` names the wall time instead and lets the
zone decide what instant that is on any given date, which is drift-free by construction.

Which dates the wall time lands on is a ``DaySelector``, one of two frozen values: ``Weekdays``
(the weekly window, the original shape) or ``MonthDays`` (days of the month, ADR-0025 monthly
addendum). A union rather than two optional fields, so "a rule has exactly one day selector" is
the shape rather than a cross-field check, and a future yearly variant joins here.

Pure like its ``schedule.py`` sibling: the zone arrives as the ``DisplayZone`` value the
composition root already builds, so this module reads an abstract ``tzinfo`` and never imports
``zoneinfo`` (the ADR-0025 display addendum's split). Reusing ``DisplayZone.resolve`` for every
candidate is the load-bearing part of that reuse: the two daylight-saving irregularities then
settle here exactly as they already settle for a naive ``at``, so one policy covers both, and
an occurrence in a spring-forward gap fires just past the gap rather than being skipped.
"""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from cortex_core.schedule_time import DisplayZone

# Monday-first, matching ``date.weekday()``; the index IS the stored weekday number.
DAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

EVERY_DAY = frozenset(range(len(DAY_NAMES)))
"""Every weekday, the default day set for a rule that names only a time."""

MAX_MONTH_DAY = 31
"""The widest a month gets; a day past it would name a date no month contains."""

_ORDINAL_SUFFIXES = {1: "st", 2: "nd", 3: "rd"}
# 11th/12th/13th take "th" despite their last digit, the one irregularity in 1..31.
_TEENS = frozenset({11, 12, 13})


def _ordinal(day: int) -> str:
    """A day of the month as an English ordinal (``1`` as ``1st``), for a listing line."""
    suffix = "th" if day in _TEENS else _ORDINAL_SUFFIXES.get(day % 10, "th")
    return f"{day}{suffix}"


@dataclass(frozen=True, slots=True)
class Weekdays:
    """The weekly day selector: which weekdays a rule's wall time fires on.

    ``days`` holds ``date.weekday()`` numbers (0 = Monday) and is **never empty**, which is
    what bounds the occurrence search to one week. Every-day is the full set rather than a
    ``None`` sentinel, so there is one representation and no second branch to carry.
    """

    days: frozenset[int] = EVERY_DAY

    def __post_init__(self) -> None:
        if not self.days:
            msg = "Weekdays.days must name at least one weekday"
            raise ValueError(msg)
        if any(day not in EVERY_DAY for day in self.days):
            msg = "Weekdays.days must hold weekday numbers 0..6"
            raise ValueError(msg)

    def describe(self) -> str:
        """One phrase for a listing line: ``every day`` / ``every mon, fri``."""
        if self.days == EVERY_DAY:
            return "every day"
        return "every " + ", ".join(DAY_NAMES[day] for day in sorted(self.days))

    def walk(self, start: date) -> tuple[list[date], date]:
        """This week's remaining occurrence dates from ``start``, plus next week's first.

        ``start`` itself leads the candidates when it is a listed weekday, because its wall
        time may still be ahead. The fallback is at least seven days out, so it is later than
        any instant whose local date is ``start`` and the search needs no other termination
        condition, which is why ``days`` is required non-empty.
        """
        offsets = sorted((day - start.weekday()) % len(DAY_NAMES) for day in self.days)
        return (
            [start + timedelta(days=offset) for offset in offsets],
            start + timedelta(days=offsets[0] + len(DAY_NAMES)),
        )


@dataclass(frozen=True, slots=True)
class MonthDays:
    """The monthly day selector: which days of the month a rule's wall time fires on.

    ``days`` holds calendar day numbers (1..``MAX_MONTH_DAY``) and is never empty, for the
    same reason ``Weekdays.days`` is not. A day the month does not have **clamps to that
    month's last day** rather than skipping the month (ADR-0025 monthly addendum): the same
    policy daylight saving already takes here, where an irregularity moves an occurrence and
    never deletes one, and a reminder that silently never fires is the worst outcome available.
    Two consequences worth naming: ``{31}`` is how "the last day of every month" is written,
    and days that clamp together (30 and 31 in February) fire once, since the walk works in
    resolved dates.
    """

    days: frozenset[int]

    def __post_init__(self) -> None:
        if not self.days:
            msg = "MonthDays.days must name at least one day of the month"
            raise ValueError(msg)
        if any(not 1 <= day <= MAX_MONTH_DAY for day in self.days):
            msg = f"MonthDays.days must hold days of the month 1..{MAX_MONTH_DAY}"
            raise ValueError(msg)

    def describe(self) -> str:
        """One phrase for a listing line: ``every month on the 1st, 15th``."""
        return "every month on the " + ", ".join(_ordinal(day) for day in sorted(self.days))

    def walk(self, start: date) -> tuple[list[date], date]:
        """This month's occurrence dates from ``start`` on, plus next month's first.

        The fallback lies in the following month, so its date is greater than ``start`` and
        therefore later than any instant ``start`` names, in any zone. That is what bounds
        this search the way seven days bounds the weekly one.
        """
        first_next = (start.replace(day=1) + timedelta(days=MAX_MONTH_DAY + 1)).replace(day=1)
        return (
            [day for day in self._dates(start.year, start.month) if day >= start],
            self._dates(first_next.year, first_next.month)[0],
        )

    def _dates(self, year: int, month: int) -> list[date]:
        """One month's occurrence dates: each listed day clamped into it, deduplicated."""
        last = monthrange(year, month)[1]
        return sorted({date(year, month, min(day, last)) for day in self.days})


DaySelector = Weekdays | MonthDays
"""Which dates a rule's wall time lands on. Closed, so the codec can enumerate the variants."""

DAILY = Weekdays()
"""Every day of the week: the default selector, and the shape a rule had before ``MonthDays``."""


@dataclass(frozen=True, slots=True)
class CalendarRule:
    """A recurring wall-clock time: ``hour``/``minute`` on each date ``on`` selects.

    The rule names a wall time, not an instant, and deliberately carries no zone of its own:
    a deployment has exactly one ``DisplayZone`` by construction, so "09:00" means 09:00 as
    this deployment renders time. Changing ``CORTEX_SCHEDULE_TZ`` therefore moves existing
    calendar schedules with it, which is the reading a single-user assistant that travels
    wants (your 09:00 follows you). A per-rule zone is the additive extension if a second
    zone ever exists; it would be a new field here, not a different shape.
    """

    hour: int
    minute: int
    on: DaySelector = DAILY

    def __post_init__(self) -> None:
        if not 0 <= self.hour <= 23:  # noqa: PLR2004 - the 24-hour clock, not a magic number
            msg = "CalendarRule.hour must be 0..23"
            raise ValueError(msg)
        if not 0 <= self.minute <= 59:  # noqa: PLR2004 - minutes per hour
            msg = "CalendarRule.minute must be 0..59"
            raise ValueError(msg)

    @property
    def wall_time(self) -> str:
        """The rule's time of day as zero-padded ``HH:MM`` (the model reads and writes this)."""
        return f"{self.hour:02d}:{self.minute:02d}"

    def describe(self) -> str:
        """One phrase for a listing line: ``every mon, fri at 07:30``, ``every month on the 1st
        at 09:00``."""
        return f"{self.on.describe()} at {self.wall_time}"


def next_calendar_due(rule: CalendarRule, after: datetime, zone: DisplayZone) -> datetime | None:
    """The rule's first occurrence strictly after ``after``, as a UTC instant.

    The search reads ``after`` as a local date and asks the rule's selector to walk from it:
    the candidates its window still holds (``after``'s own date leads them, since its wall time
    may still be ahead), then one fallback that is later than any instant that date names. The
    fallback is what makes the walk total without a defensive iteration cap.

    Every candidate is resolved through ``DisplayZone.resolve``, so the rule follows daylight
    saving rather than drifting against it and both irregular cases inherit the documented
    policy: an occurrence inside a **spring-forward gap** lands just past the gap (fires late,
    never skipped), and one in a **fall-back repeat** takes the earlier offset, so a repeated
    wall hour fires once rather than twice. Returns ``None`` when the next occurrence is past
    ``datetime.max``, matching ``next_due``: the recurrence ends rather than re-arming a fire
    that could never persist.
    """
    try:
        start = after.astimezone(zone.tz).date()
        wall = time(hour=rule.hour, minute=rule.minute)
        candidates, wrapped = rule.on.walk(start)
        for candidate in candidates:
            instant = zone.resolve(datetime.combine(candidate, wall))
            if instant > after:
                return instant
        # Every candidate the window still held has passed, so the next occurrence is the
        # selector's fallback: next week's first listed weekday, or next month's first day.
        return zone.resolve(datetime.combine(wrapped, wall))
    except (OverflowError, ValueError):
        return None
