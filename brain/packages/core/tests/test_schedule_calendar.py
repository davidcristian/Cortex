"""CalendarRule and the wall-clock occurrence math (ADR-0025 calendar addendum).

Like ``test_schedule_time.py``, the daylight-saving cases run against a real ``ZoneInfo``
rather than a fixed-offset fake: a rule that "follows the wall clock" is only meaningfully
tested in a zone that actually transitions, and the whole point of the shape is the behavior
an interval gets wrong there. Europe/Bucharest is +02:00 in winter and +03:00 in summer, with
both 2026 transitions landing on a 03:00-04:00 local window.
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from cortex_core import UTC_DISPLAY, CalendarRule, DisplayZone
from cortex_core.schedule_calendar import DAY_NAMES, EVERY_DAY, next_calendar_due

_BUCHAREST = DisplayZone(name="Europe/Bucharest", tz=ZoneInfo("Europe/Bucharest"))
# Behind UTC, so its local date can be a day *earlier* than the UTC one: the mirror of
# Bucharest, and the only direction in which reading the wrong date changes an answer.
_LOS_ANGELES = DisplayZone(name="America/Los_Angeles", tz=ZoneInfo("America/Los_Angeles"))

_MON, _TUE, _WED, _THU, _FRI = range(5)
_WEEKDAYS = frozenset({_MON, _TUE, _WED, _THU, _FRI})


def _utc(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def test_a_rule_defaults_to_every_day() -> None:
    assert CalendarRule(hour=9, minute=0).days == EVERY_DAY
    assert len(EVERY_DAY) == len(DAY_NAMES)


@pytest.mark.parametrize(
    ("hour", "minute", "days"),
    [
        (24, 0, EVERY_DAY),  # hour past the 24-hour clock
        (-1, 0, EVERY_DAY),
        (9, 60, EVERY_DAY),  # minute past the hour
        (9, -1, EVERY_DAY),
        (9, 0, frozenset[int]()),  # empty: would make the occurrence search unbounded
        (9, 0, frozenset({7})),  # not a date.weekday() number
    ],
)
def test_a_rule_rejects_an_unusable_shape(hour: int, minute: int, days: frozenset[int]) -> None:
    """Each invariant is enforced at construction, so no later stage has to re-check it."""
    with pytest.raises(ValueError, match="CalendarRule"):
        CalendarRule(hour=hour, minute=minute, days=days)


def test_describe_names_every_day_without_listing_seven_of_them() -> None:
    assert CalendarRule(hour=9, minute=0).describe() == "every day at 09:00"


def test_describe_lists_a_restricted_day_set_in_week_order() -> None:
    rule = CalendarRule(hour=7, minute=30, days=frozenset({_FRI, _MON}))
    assert rule.describe() == "every mon, fri at 07:30"


def test_the_wall_time_is_zero_padded() -> None:
    assert CalendarRule(hour=7, minute=5).wall_time == "07:05"


def test_todays_occurrence_is_next_when_its_wall_time_is_still_ahead() -> None:
    rule = CalendarRule(hour=9, minute=0)
    assert next_calendar_due(rule, _utc(2026, 7, 20, 6, 0), UTC_DISPLAY) == _utc(2026, 7, 20, 9)


def test_tomorrows_occurrence_is_next_once_todays_has_passed() -> None:
    rule = CalendarRule(hour=9, minute=0)
    assert next_calendar_due(rule, _utc(2026, 7, 20, 12, 0), UTC_DISPLAY) == _utc(2026, 7, 21, 9)


def test_the_occurrence_is_strictly_after_so_firing_does_not_re_arm_in_place() -> None:
    """Exactly at the wall time means the *next* one; otherwise a fire would re-arm on itself."""
    rule = CalendarRule(hour=9, minute=0)
    fired_at = _utc(2026, 7, 20, 9, 0)
    assert next_calendar_due(rule, fired_at, UTC_DISPLAY) == _utc(2026, 7, 21, 9)


def test_a_restricted_day_set_skips_to_the_next_listed_weekday() -> None:
    """2026-07-18 is a Saturday, so a weekdays-only rule jumps the weekend to Monday."""
    rule = CalendarRule(hour=9, minute=0, days=_WEEKDAYS)
    assert next_calendar_due(rule, _utc(2026, 7, 18, 12, 0), UTC_DISPLAY) == _utc(2026, 7, 20, 9)


def test_the_search_wraps_into_the_following_week() -> None:
    """A Monday-only rule, asked on a Monday past its time, lands on the next Monday."""
    rule = CalendarRule(hour=9, minute=0, days=frozenset({_MON}))
    monday_afternoon = _utc(2026, 7, 20, 15, 0)
    assert monday_afternoon.weekday() == _MON
    assert next_calendar_due(rule, monday_afternoon, UTC_DISPLAY) == _utc(2026, 7, 27, 9)


def test_the_local_date_drives_the_search_not_the_utc_date() -> None:
    """23:00 UTC is already the next day in Bucharest, so "tomorrow" is read locally."""
    rule = CalendarRule(hour=9, minute=0)
    # 2026-07-20T23:00Z is 2026-07-21T02:00 local, so the next 09:00 local is that same day.
    assert next_calendar_due(rule, _utc(2026, 7, 20, 23, 0), _BUCHAREST) == _utc(2026, 7, 21, 6)


def test_a_zone_behind_utc_reads_its_own_weekday_not_the_utc_one() -> None:
    """The direction that actually bites: west of UTC, the UTC date is already *tomorrow*.

    At 2026-07-21T02:00Z it is still Monday 19:00 in Los Angeles, so a Monday 21:00 rule fires
    in two hours. Reading the UTC date instead would see Tuesday, find no Monday left this
    week, and push the reminder a full week out. A zone ahead of UTC cannot catch this,
    because starting the search a day early only adds candidates the ``> after`` filter drops.
    """
    rule = CalendarRule(hour=21, minute=0, days=frozenset({_MON}))
    after = _utc(2026, 7, 21, 2, 0)
    assert after.astimezone(_LOS_ANGELES.tz).weekday() == _MON  # local Monday, UTC Tuesday
    assert next_calendar_due(rule, after, _LOS_ANGELES) == _utc(2026, 7, 21, 4, 0)


def test_the_wall_time_holds_across_a_spring_forward_transition() -> None:
    """The headline property: 09:00 stays 09:00, which a fixed 24 h interval cannot do.

    Bucharest springs forward on 2026-03-29, so the two consecutive 09:00 local occurrences
    are 23 hours apart in absolute time. An ``every=timedelta(days=1)`` item would have
    re-armed at 07:00 UTC, which is 10:00 local: an hour of drift the user would notice.
    """
    rule = CalendarRule(hour=9, minute=0)
    before = _utc(2026, 3, 28, 7, 0)  # 09:00+02:00
    assert _BUCHAREST.render(before) == "2026-03-28T09:00:00+02:00"
    after = next_calendar_due(rule, before, _BUCHAREST)
    assert after is not None
    assert after == _utc(2026, 3, 29, 6, 0)  # 09:00+03:00, 23 hours later
    assert _BUCHAREST.render(after) == "2026-03-29T09:00:00+03:00"


def test_the_wall_time_holds_across_a_fall_back_transition() -> None:
    """The mirror case: 25 hours between occurrences, wall time unmoved."""
    rule = CalendarRule(hour=9, minute=0)
    before = _utc(2026, 10, 24, 6, 0)  # 09:00+03:00
    after = next_calendar_due(rule, before, _BUCHAREST)
    assert after is not None
    assert after == _utc(2026, 10, 25, 7, 0)  # 09:00+02:00, 25 hours later
    assert _BUCHAREST.render(after) == "2026-10-25T09:00:00+02:00"


def test_an_occurrence_inside_a_spring_forward_gap_fires_just_past_the_gap() -> None:
    """03:30 does not exist on 2026-03-29; the rule fires late rather than skipping a day.

    This inherits ``DisplayZone.resolve``'s documented fold policy rather than adding a
    second one, so a gap occurrence and a gap ``at`` settle identically.
    """
    rule = CalendarRule(hour=3, minute=30)
    due = next_calendar_due(rule, _utc(2026, 3, 28, 12, 0), _BUCHAREST)
    assert due is not None
    assert due == _utc(2026, 3, 29, 1, 30)
    assert _BUCHAREST.render(due) == "2026-03-29T04:30:00+03:00"


def test_a_repeated_wall_hour_fires_once_not_twice() -> None:
    """Fall back repeats 03:30 on 2026-10-25; ``fold=0`` takes the earlier of the two.

    Having fired at that earlier instant, the next occurrence is the following day, never the
    second 03:30 an hour later, so the user gets one reminder rather than two.
    """
    rule = CalendarRule(hour=3, minute=30)
    first = next_calendar_due(rule, _utc(2026, 10, 25, 0, 0), _BUCHAREST)
    assert first is not None
    assert first == _utc(2026, 10, 25, 0, 30)  # 03:30+03:00, the earlier reading
    assert next_calendar_due(rule, first, _BUCHAREST) == _utc(2026, 10, 26, 1, 30)


def test_an_occurrence_past_the_representable_maximum_ends_the_recurrence() -> None:
    """``None`` matches ``next_due``: terminal beats a re-arm that could never persist."""
    rule = CalendarRule(hour=23, minute=30)
    # Today's 23:30 has already passed, so the search steps to a date past date.max.
    assert next_calendar_due(rule, _utc(9999, 12, 31, 23, 59), UTC_DISPLAY) is None
