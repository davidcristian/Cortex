"""Calendar recurrence: a wall-clock rule and the zone-aware occurrence math (ADR-0025)."""

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
    """The weekly day selector: which weekdays a rule's wall time fires on."""

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
        """This week's remaining occurrence dates from ``start``, plus next week's first."""
        offsets = sorted((day - start.weekday()) % len(DAY_NAMES) for day in self.days)
        return (
            [start + timedelta(days=offset) for offset in offsets],
            start + timedelta(days=offsets[0] + len(DAY_NAMES)),
        )


@dataclass(frozen=True, slots=True)
class MonthDays:
    """The monthly day selector: which days of the month a rule's wall time fires on."""

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
        """This month's occurrence dates from ``start`` on, plus next month's first."""
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
    """A recurring wall-clock time: ``hour``/``minute`` on each date ``on`` selects."""

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
    """The rule's first occurrence strictly after ``after``, as a UTC instant."""
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
