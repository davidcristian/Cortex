"""Which dates a calendar rule's wall time lands on: the ``DaySelector`` union (ADR-0025).

Split from ``schedule_calendar.py`` at the 300-line cap when yearly rules landed (ADR-0025
yearly addendum), along the responsibility line the union itself draws: *which dates* a rule
selects lives here, while the rule that names a wall time and the zone-aware occurrence math
that resolves it stay there. The two are read together but change for different reasons, and
a fourth selector would land here alone.

Three frozen variants, one per cycle a wall-clock rule can name: ``Weekdays`` (the weekly
window, the original shape), ``MonthDays`` (days of the month, ADR-0025 monthly addendum), and
``YearDays`` (calendar dates, ADR-0025 yearly addendum). A closed union rather than parallel
optional fields on the rule, so "a rule has exactly one day selector" is the shape rather than
a cross-field check, and the codec can enumerate the variants.

Each answers one question, ``walk(start) -> (candidates, wrapped)``: the dates from ``start``
onward that its own window contains, plus one fallback unconditionally later than any instant
whose local date is ``start``. That contract is what keeps the occurrence search total by
construction, with no defensive iteration cap and so no unreachable branch to fake coverage
over, which is why every selector's day set is required non-empty.

Pure: dates and sets only, no clock, no zone, no I/O.
"""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta

# Monday-first, matching ``date.weekday()``; the index IS the stored weekday number.
DAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

EVERY_DAY = frozenset(range(len(DAY_NAMES)))
"""Every weekday, the default day set for a rule that names only a time."""

MAX_MONTH_DAY = 31
"""The widest a month gets; a day past it would name a date no month contains."""

MONTH_NAMES = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
"""Month abbreviations for a listing line. Defined here, not taken from ``calendar``, whose
``month_abbr`` follows the process locale and would render a schedule differently per host."""

_MONTH_LENGTHS = (31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
# February at its LEAP-year length: the longest each month ever gets, which is what bounds a
# named date. 29 February is a real date that clamps in common years; 30 February is not.

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


@dataclass(frozen=True, slots=True, order=True)
class MonthDay:
    """One date within a year: a month and a day, with no year of its own.

    Ordered, and deliberately month-first, so sorting a set of these **is** putting them in
    chronological order within the year, which both the occurrence walk and the listing line
    rely on rather than re-deriving. ``day`` is bounded by the longest that month ever gets,
    so 29 February constructs (a real date that clamps in common years) while 30 February does
    not (a date no year contains, and so certainly a mistake rather than a clamp request).
    """

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
        """This date in ``year``, clamped to the month's real length (29 February in a common
        year becomes the 28th), matching how ``MonthDays`` clamps a day its month lacks."""
        return date(year, self.month, min(self.day, monthrange(year, self.month)[1]))


@dataclass(frozen=True, slots=True)
class YearDays:
    """The yearly day selector: which calendar dates a rule's wall time fires on.

    ``days`` holds ``MonthDay`` pairs and is never empty, for the same reason its siblings'
    day sets are not. A **set of pairs** rather than one month alongside a day set (which is
    what the monthly addendum predicted): holidays, renewals, and birthdays cluster across
    months rather than within one, so "25 December and 1 January" is the common shape and the
    single-month form is reachable anyway as pairs sharing a month.

    29 February clamps to the 28th in a common year rather than skipping three years in four,
    inheriting the clamp policy from ``MonthDays`` and, before it, from daylight saving: a
    calendar irregularity moves an occurrence and never deletes one.
    """

    days: frozenset[MonthDay]

    def __post_init__(self) -> None:
        if not self.days:
            msg = "YearDays.days must name at least one date"
            raise ValueError(msg)

    def describe(self) -> str:
        """One phrase for a listing line: ``every year on 1 jan, 25 dec``."""
        return "every year on " + ", ".join(day.describe() for day in sorted(self.days))

    def walk(self, start: date) -> tuple[list[date], date]:
        """This year's occurrence dates from ``start`` on, plus next year's first.

        The fallback lies in the following year, so it is later than any instant ``start``
        names, in any zone. That is what bounds this search the way seven days bounds the
        weekly one and the next month bounds the monthly one. Past ``date.max`` it raises
        rather than looping, which ``next_calendar_due`` already answers as a recurrence that
        has ended.

        The ``>= start`` narrowing is an optimization, not the strictness guard, and the same
        is true of ``MonthDays``: an earlier date can only resolve to an earlier instant (a
        daylight-saving fold moves an occurrence by an hour, never across a day), so
        ``next_calendar_due``'s ``instant > after`` test is what actually enforces "strictly
        after". Dropping it here leaves every test green, so it is deliberately not claimed as
        a mutation-proven guard; it keeps this contract locally true and saves resolutions.
        """
        return (
            [day for day in self._dates(start.year) if day >= start],
            self._dates(start.year + 1)[0],
        )

    def _dates(self, year: int) -> list[date]:
        """One year's occurrence dates: each named date resolved into it, deduplicated.

        Dates that clamp together (29 and 28 February in a common year) fire once, since the
        walk works in resolved dates, exactly as the monthly selector's collisions do.
        """
        return sorted({day.resolve(year) for day in self.days})


DaySelector = Weekdays | MonthDays | YearDays
"""Which dates a rule's wall time lands on. Closed, so the codec can enumerate the variants."""

DAILY = Weekdays()
"""Every day of the week: the default selector, and the shape a rule had before ``MonthDays``."""
