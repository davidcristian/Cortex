"""Calendar recurrence: a wall-clock rule and the zone-aware occurrence math (ADR-0025)."""

from dataclasses import dataclass
from datetime import datetime, time, timedelta

from cortex_core.schedule_time import DisplayZone

# Monday-first, matching ``date.weekday()``; the index IS the stored weekday number.
DAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

EVERY_DAY = frozenset(range(len(DAY_NAMES)))
"""Every weekday, the default day set for a rule that names only a time."""


@dataclass(frozen=True, slots=True)
class CalendarRule:
    """A recurring wall-clock time: ``hour``/``minute`` on each weekday in ``days``."""

    hour: int
    minute: int
    days: frozenset[int] = EVERY_DAY

    def __post_init__(self) -> None:
        if not 0 <= self.hour <= 23:  # noqa: PLR2004 - the 24-hour clock, not a magic number
            msg = "CalendarRule.hour must be 0..23"
            raise ValueError(msg)
        if not 0 <= self.minute <= 59:  # noqa: PLR2004 - minutes per hour
            msg = "CalendarRule.minute must be 0..59"
            raise ValueError(msg)
        if not self.days:
            msg = "CalendarRule.days must name at least one weekday"
            raise ValueError(msg)
        if any(day not in EVERY_DAY for day in self.days):
            msg = "CalendarRule.days must hold weekday numbers 0..6"
            raise ValueError(msg)

    @property
    def wall_time(self) -> str:
        """The rule's time of day as zero-padded ``HH:MM`` (the model reads and writes this)."""
        return f"{self.hour:02d}:{self.minute:02d}"

    def describe(self) -> str:
        """One phrase for a listing line: ``every day at 09:00`` / ``every mon, fri at 07:30``."""
        if self.days == EVERY_DAY:
            return f"every day at {self.wall_time}"
        named = ", ".join(DAY_NAMES[day] for day in sorted(self.days))
        return f"every {named} at {self.wall_time}"


def next_calendar_due(rule: CalendarRule, after: datetime, zone: DisplayZone) -> datetime | None:
    """The rule's first occurrence strictly after ``after``, as a UTC instant."""
    try:
        start = after.astimezone(zone.tz).date()
        wall = time(hour=rule.hour, minute=rule.minute)
        offsets = sorted((day - start.weekday()) % len(DAY_NAMES) for day in rule.days)
        for offset in offsets:
            instant = zone.resolve(datetime.combine(start + timedelta(days=offset), wall))
            if instant > after:
                return instant
        # Every listed weekday from today on has already passed its wall time today, so the
        # next occurrence is the earliest listed weekday of the following week.
        wrapped = start + timedelta(days=offsets[0] + len(DAY_NAMES))
        return zone.resolve(datetime.combine(wrapped, wall))
    except (OverflowError, ValueError):
        return None
