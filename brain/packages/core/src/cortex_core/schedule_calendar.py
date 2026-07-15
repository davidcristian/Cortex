"""Calendar recurrence: a wall-clock rule and the zone-aware occurrence math (ADR-0025).

The second recurrence *shape*, beside ``ScheduledItem.every``. An interval is the wrong tool
for "every weekday at 09:00": ``every`` is a ``timedelta`` while a calendar day is 23, 24, or
25 hours long depending on daylight saving, so a fixed interval drifts off the wall clock
exactly when a user notices. A ``CalendarRule`` names the wall time instead and lets the
zone decide what instant that is on any given date, which is drift-free by construction.

Which dates the wall time lands on is a ``DaySelector`` (weekly, monthly, or yearly), which
lives in ``schedule_selectors.py`` since the yearly variant split it out at the 300-line cap.
This module owns the rule and the occurrence math over whatever a selector answers, so it
reads the union through one call (``walk``) and never enumerates its variants.

Pure like its ``schedule.py`` sibling: the zone arrives as the ``DisplayZone`` value the
composition root already builds, so this module reads an abstract ``tzinfo`` and never imports
``zoneinfo`` (the ADR-0025 display addendum's split). Reusing ``DisplayZone.resolve`` for every
candidate is the load-bearing part of that reuse: the two daylight-saving irregularities then
settle here exactly as they already settle for a naive ``at``, so one policy covers both, and
an occurrence in a spring-forward gap fires just past the gap rather than being skipped.
"""

from dataclasses import dataclass
from datetime import datetime, time

from cortex_core.schedule_selectors import DAILY, DaySelector
from cortex_core.schedule_time import DisplayZone


@dataclass(frozen=True, slots=True)
class CalendarRule:
    """A recurring wall-clock time: ``hour``/``minute`` on each date ``on`` selects.

    The rule names a wall time, not an instant. ``zone`` is the zone that wall time means: with
    it set, the rule fires at ``hour``:``minute`` in ``zone`` regardless of the deployment's
    ``CORTEX_SCHEDULE_TZ``, so a user in one place can pin a reminder to another (ADR-0025
    per-rule addendum). Left ``None`` the rule takes the deployment zone the occurrence math is
    handed, which is the default a single-user assistant that travels wants: changing
    ``CORTEX_SCHEDULE_TZ`` moves a zone-less rule with it (your 09:00 follows you), while a rule
    that named its own zone stays put. The rule holds the resolved ``DisplayZone``; only its
    name is durable, so the codec stores the name and reconstructs the zone on decode.
    """

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
        """One phrase for a listing line: ``every mon, fri at 07:30``, ``every month on the 1st
        at 09:00``, ``every year on 25 dec at 09:00``; a per-rule zone is named in parentheses
        (``every day at 09:00 (America/New_York)``) so a bare wall time is never ambiguous."""
        zone = f" ({self.zone.name})" if self.zone is not None else ""
        return f"{self.on.describe()} at {self.wall_time}{zone}"


def next_calendar_due(rule: CalendarRule, after: datetime, zone: DisplayZone) -> datetime | None:
    """The rule's first occurrence strictly after ``after``, as a UTC instant.

    The rule's own ``zone`` governs when it has one, and the passed deployment ``zone`` otherwise
    (ADR-0025 per-rule addendum): a rule that named a zone fires at that zone's wall clock no
    matter where the deployment renders, while a zone-less rule follows ``CORTEX_SCHEDULE_TZ``.

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
    effective = rule.zone if rule.zone is not None else zone
    try:
        start = after.astimezone(effective.tz).date()
        wall = time(hour=rule.hour, minute=rule.minute)
        candidates, wrapped = rule.on.walk(start)
        for candidate in candidates:
            instant = effective.resolve(datetime.combine(candidate, wall))
            if instant > after:
                return instant
        # Every candidate the window still held has passed, so the next occurrence is the
        # selector's fallback: next week's, next month's, or next year's first listed date.
        return effective.resolve(datetime.combine(wrapped, wall))
    except (OverflowError, ValueError):
        return None
