"""Calendar recurrence: a wall-clock rule and the zone-aware occurrence math (ADR-0025).

The second recurrence *shape*, beside ``ScheduledItem.every``. An interval is the wrong tool
for "every weekday at 09:00": ``every`` is a ``timedelta`` while a calendar day is 23, 24, or
25 hours long depending on daylight saving, so a fixed interval drifts off the wall clock
exactly when a user notices. A ``CalendarRule`` names the wall time instead and lets the
zone decide what instant that is on any given date, which is drift-free by construction.

Pure like its ``schedule.py`` sibling: the zone arrives as the ``DisplayZone`` value the
composition root already builds, so this module reads an abstract ``tzinfo`` and never imports
``zoneinfo`` (the ADR-0025 display addendum's split). Reusing ``DisplayZone.resolve`` for every
candidate is the load-bearing part of that reuse: the two daylight-saving irregularities then
settle here exactly as they already settle for a naive ``at``, so one policy covers both, and
an occurrence in a spring-forward gap fires just past the gap rather than being skipped.
"""

from dataclasses import dataclass
from datetime import datetime, time, timedelta

from cortex_core.schedule_time import DisplayZone

# Monday-first, matching ``date.weekday()``; the index IS the stored weekday number.
DAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

EVERY_DAY = frozenset(range(len(DAY_NAMES)))
"""Every weekday, the default day set for a rule that names only a time."""


@dataclass(frozen=True, slots=True)
class CalendarRule:
    """A recurring wall-clock time: ``hour``/``minute`` on each weekday in ``days``.

    ``days`` holds ``date.weekday()`` numbers (0 = Monday) and is **never empty**, which is
    what bounds the occurrence search to one week. Every-day is the full set rather than a
    ``None`` sentinel, so there is one representation and no second branch to carry.

    The rule names a wall time, not an instant, and deliberately carries no zone of its own:
    a deployment has exactly one ``DisplayZone`` by construction, so "09:00" means 09:00 as
    this deployment renders time. Changing ``CORTEX_SCHEDULE_TZ`` therefore moves existing
    calendar schedules with it, which is the reading a single-user assistant that travels
    wants (your 09:00 follows you). A per-rule zone is the additive extension if a second
    zone ever exists; it would be a new field here, not a different shape.
    """

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
    """The rule's first occurrence strictly after ``after``, as a UTC instant.

    The search reads ``after`` as a local date, then walks the rule's own weekdays: today
    first (its wall time may still be ahead), then each later listed weekday this week, and
    finally the earliest listed weekday of the following week. That last candidate is at
    least seven days out, so it is unconditionally after ``after`` and the walk needs no
    other termination condition, which is why ``days`` is required non-empty.

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
