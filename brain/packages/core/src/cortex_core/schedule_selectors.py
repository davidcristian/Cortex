"""Which dates a calendar rule's wall time falls on: the ``DaySelector`` union."""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta

# Monday first, matching ``date.weekday()``: the index is the stored weekday number.
DAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

EVERY_DAY = frozenset(range(len(DAY_NAMES)))
"""Every weekday, the default day set for a rule that names only a time."""

MAX_MONTH_DAY = 31
"""The widest a month gets; a day past it would name a date no month contains."""

MONTH_NAMES = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
"""Month abbreviations for a listing line. Defined here, not taken from ``calendar``, whose
``month_abbr`` follows the process locale and would render a schedule differently per host."""

# February is at its leap-year length, so each entry is the longest that month ever gets.
# 29 February is a real date that clamps in a common year; 30 February is not.
_MONTH_LENGTHS = (31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)

_ORDINAL_SUFFIXES = {1: "st", 2: "nd", 3: "rd"}
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


@dataclass(frozen=True, slots=True, order=True)
class MonthDay:
    """One date within a year: a month and a day, with no year of its own."""

    month: int
    day: int

    def __post_init__(self) -> None:
        if not 1 <= self.month <= len(MONTH_NAMES):
            msg = f"MonthDay.month must be 1..{len(MONTH_NAMES)}"
            raise ValueError(msg)
        if not 1 <= self.day <= _MONTH_LENGTHS[self.month - 1]:
            msg = (
                f"MonthDay.day must be 1..{_MONTH_LENGTHS[self.month - 1]} "
                f"for {MONTH_NAMES[self.month - 1]}"
            )
            raise ValueError(msg)

    def describe(self) -> str:
        """The date as a listing line writes it: ``25 dec``."""
        return f"{self.day} {MONTH_NAMES[self.month - 1]}"

    def resolve(self, year: int) -> date:
        """This date in ``year``, clamped to the month's real length (29 February in a common year
        becomes the 28th), matching how ``MonthDays`` clamps a day its month lacks.
        """
        return date(year, self.month, min(self.day, monthrange(year, self.month)[1]))


@dataclass(frozen=True, slots=True)
class YearDays:
    """The yearly day selector: which calendar dates a rule's wall time fires on."""

    days: frozenset[MonthDay]

    def __post_init__(self) -> None:
        if not self.days:
            msg = "YearDays.days must name at least one date"
            raise ValueError(msg)

    def describe(self) -> str:
        """One phrase for a listing line: ``every year on 1 jan, 25 dec``."""
        return "every year on " + ", ".join(day.describe() for day in sorted(self.days))

    def walk(self, start: date) -> tuple[list[date], date]:
        """This year's occurrence dates from ``start`` on, plus next year's first."""
        return (
            [day for day in self._dates(start.year) if day >= start],
            self._dates(start.year + 1)[0],
        )

    def _dates(self, year: int) -> list[date]:
        """One year's occurrence dates: each named date resolved into it, deduplicated."""
        return sorted({day.resolve(year) for day in self.days})


DaySelector = Weekdays | MonthDays | YearDays
"""Which dates a rule's wall time lands on. Closed, so the codec can enumerate the variants."""

DAILY = Weekdays()
"""Every day of the week: the default selector, and the shape a rule had before ``MonthDays``."""
