"""Calendar recurrence: a wall-clock rule and the zone-aware occurrence math (ADR-0025)."""

from dataclasses import dataclass
from datetime import datetime, time

from cortex_core.schedule_selectors import DAILY, DaySelector
from cortex_core.schedule_time import DisplayZone


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
        at 09:00``, ``every year on 25 dec at 09:00``."""
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
        # selector's fallback: next week's, next month's, or next year's first listed date.
        return zone.resolve(datetime.combine(wrapped, wall))
    except (OverflowError, ValueError):
        return None
