"""Calendar recurrence: a wall-clock rule and the zone-aware occurrence math."""

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
    zone: DisplayZone | None = None

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
        """One phrase for a listing line, such as ``every mon, fri at 07:30``. A rule with
        its own zone names it in parentheses, so a bare wall time is never ambiguous.
        """
        zone = f" ({self.zone.name})" if self.zone is not None else ""
        return f"{self.on.describe()} at {self.wall_time}{zone}"


def next_calendar_due(rule: CalendarRule, after: datetime, zone: DisplayZone) -> datetime | None:
    """The rule's first occurrence strictly after ``after``, as a UTC instant."""
    effective = rule.zone if rule.zone is not None else zone
    try:
        start = after.astimezone(effective.tz).date()
        wall = time(hour=rule.hour, minute=rule.minute)
        candidates, wrapped = rule.on.walk(start)
        for candidate in candidates:
            instant = effective.resolve(datetime.combine(candidate, wall))
            if instant > after:
                return instant
        # No candidate in the current window is still ahead, so the next occurrence is the
        # selector's wrapped date: next week's, next month's, or next year's first date.
        return effective.resolve(datetime.combine(wrapped, wall))
    except (OverflowError, ValueError):
        return None
