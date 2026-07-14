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

from cortex_core import UTC_DISPLAY, CalendarRule, DisplayZone, MonthDays, Weekdays
from cortex_core.schedule_calendar import (
    DAILY,
    DAY_NAMES,
    EVERY_DAY,
    MAX_MONTH_DAY,
    next_calendar_due,
)

_BUCHAREST = DisplayZone(name="Europe/Bucharest", tz=ZoneInfo("Europe/Bucharest"))
# Behind UTC, so its local date can be a day *earlier* than the UTC one: the mirror of
# Bucharest, and the only direction in which reading the wrong date changes an answer.
_LOS_ANGELES = DisplayZone(name="America/Los_Angeles", tz=ZoneInfo("America/Los_Angeles"))

_MON, _TUE, _WED, _THU, _FRI = range(5)
_WEEKDAYS = frozenset({_MON, _TUE, _WED, _THU, _FRI})


def _utc(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def test_a_rule_defaults_to_every_day() -> None:
    assert CalendarRule(hour=9, minute=0).on == DAILY
    assert DAILY.days == EVERY_DAY
    assert len(EVERY_DAY) == len(DAY_NAMES)


@pytest.mark.parametrize(("hour", "minute"), [(24, 0), (-1, 0), (9, 60), (9, -1)])
def test_a_rule_rejects_a_wall_time_off_the_clock(hour: int, minute: int) -> None:
    """Each invariant is enforced at construction, so no later stage has to re-check it."""
    with pytest.raises(ValueError, match="CalendarRule"):
        CalendarRule(hour=hour, minute=minute)


@pytest.mark.parametrize(
    "days",
    [
        frozenset[int](),  # empty: would make the occurrence search unbounded
        frozenset({7}),  # not a date.weekday() number
    ],
)
def test_a_weekday_selector_rejects_an_unusable_day_set(days: frozenset[int]) -> None:
    with pytest.raises(ValueError, match="Weekdays"):
        Weekdays(days=days)


@pytest.mark.parametrize(
    "days",
    [
        frozenset[int](),  # empty: the monthly search is bounded the same way
        frozenset({0}),  # months are 1-indexed
        frozenset({MAX_MONTH_DAY + 1}),  # a day no month contains
    ],
)
def test_a_month_day_selector_rejects_an_unusable_day_set(days: frozenset[int]) -> None:
    with pytest.raises(ValueError, match="MonthDays"):
        MonthDays(days=days)


def test_describe_names_every_day_without_listing_seven_of_them() -> None:
    assert CalendarRule(hour=9, minute=0).describe() == "every day at 09:00"


def test_describe_lists_a_restricted_day_set_in_week_order() -> None:
    rule = CalendarRule(hour=7, minute=30, on=Weekdays(days=frozenset({_FRI, _MON})))
    assert rule.describe() == "every mon, fri at 07:30"


def test_describe_names_month_days_as_ordinals_in_order() -> None:
    rule = CalendarRule(hour=9, minute=0, on=MonthDays(days=frozenset({15, 1})))
    assert rule.describe() == "every month on the 1st, 15th at 09:00"


@pytest.mark.parametrize(
    ("day", "ordinal"),
    [
        (1, "1st"),
        (2, "2nd"),
        (3, "3rd"),
        (4, "4th"),
        (11, "11th"),  # the teens take "th" despite ending in 1, 2, 3
        (12, "12th"),
        (13, "13th"),
        (21, "21st"),
        (22, "22nd"),
        (23, "23rd"),
        (MAX_MONTH_DAY, "31st"),
    ],
)
def test_a_month_day_reads_as_an_english_ordinal(day: int, ordinal: str) -> None:
    assert MonthDays(days=frozenset({day})).describe() == f"every month on the {ordinal}"


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
    rule = CalendarRule(hour=9, minute=0, on=Weekdays(days=_WEEKDAYS))
    assert next_calendar_due(rule, _utc(2026, 7, 18, 12, 0), UTC_DISPLAY) == _utc(2026, 7, 20, 9)


def test_the_search_wraps_into_the_following_week() -> None:
    """A Monday-only rule, asked on a Monday past its time, lands on the next Monday."""
    rule = CalendarRule(hour=9, minute=0, on=Weekdays(days=frozenset({_MON})))
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
    rule = CalendarRule(hour=21, minute=0, on=Weekdays(days=frozenset({_MON})))
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


def test_todays_month_day_occurrence_is_next_when_its_wall_time_is_still_ahead() -> None:
    rule = CalendarRule(hour=9, minute=0, on=MonthDays(days=frozenset({20})))
    assert next_calendar_due(rule, _utc(2026, 7, 20, 6, 0), UTC_DISPLAY) == _utc(2026, 7, 20, 9)


def test_the_month_search_moves_to_the_next_listed_day_of_the_same_month() -> None:
    rule = CalendarRule(hour=9, minute=0, on=MonthDays(days=frozenset({1, 15})))
    assert next_calendar_due(rule, _utc(2026, 7, 2, 12, 0), UTC_DISPLAY) == _utc(2026, 7, 15, 9)


def test_the_month_search_wraps_into_the_following_month() -> None:
    """A 1st-of-the-month rule asked mid-month has no candidate left, so it takes the fallback."""
    rule = CalendarRule(hour=9, minute=0, on=MonthDays(days=frozenset({1})))
    assert next_calendar_due(rule, _utc(2026, 7, 15, 12, 0), UTC_DISPLAY) == _utc(2026, 8, 1, 9)


def test_the_month_search_wraps_across_a_year_boundary() -> None:
    """December's fallback is January of the next year, which the month arithmetic must reach."""
    rule = CalendarRule(hour=9, minute=0, on=MonthDays(days=frozenset({1})))
    assert next_calendar_due(rule, _utc(2026, 12, 15, 12, 0), UTC_DISPLAY) == _utc(2027, 1, 1, 9)


def test_a_month_day_occurrence_is_strictly_after_so_firing_does_not_re_arm_in_place() -> None:
    rule = CalendarRule(hour=9, minute=0, on=MonthDays(days=frozenset({20})))
    fired_at = _utc(2026, 7, 20, 9, 0)
    assert next_calendar_due(rule, fired_at, UTC_DISPLAY) == _utc(2026, 8, 20, 9)


def test_a_day_a_short_month_lacks_fires_on_that_months_last_day() -> None:
    """The clamping policy: February has no 31st, so a 31st rule fires on the 28th.

    Skipping the month instead would mean a monthly reminder silently never arrives, which is
    the one outcome worse than firing a few days early. It also makes ``[31]`` the way to say
    "the last day of every month" without a second selector.
    """
    rule = CalendarRule(hour=9, minute=0, on=MonthDays(days=frozenset({MAX_MONTH_DAY})))
    assert next_calendar_due(rule, _utc(2026, 2, 10, 12, 0), UTC_DISPLAY) == _utc(2026, 2, 28, 9)
    # April has 30 days, so the same rule lands one day earlier there.
    assert next_calendar_due(rule, _utc(2026, 4, 10, 12, 0), UTC_DISPLAY) == _utc(2026, 4, 30, 9)


def test_the_clamp_follows_the_leap_year_rather_than_a_fixed_february() -> None:
    """2028 is a leap year, so the same rule reaches the 29th there and the 28th in 2026."""
    rule = CalendarRule(hour=9, minute=0, on=MonthDays(days=frozenset({MAX_MONTH_DAY})))
    assert next_calendar_due(rule, _utc(2028, 2, 10, 12, 0), UTC_DISPLAY) == _utc(2028, 2, 29, 9)


def test_days_that_clamp_together_fire_once_not_twice() -> None:
    """30 and 31 both land on 28 February; the walk works in resolved dates, so it fires once."""
    rule = CalendarRule(hour=9, minute=0, on=MonthDays(days=frozenset({30, MAX_MONTH_DAY})))
    february = next_calendar_due(rule, _utc(2026, 2, 10, 12, 0), UTC_DISPLAY)
    assert february is not None
    assert february == _utc(2026, 2, 28, 9)
    # The next occurrence leaves February entirely rather than repeating its last day.
    assert next_calendar_due(rule, february, UTC_DISPLAY) == _utc(2026, 3, 30, 9)


def test_a_month_day_rule_reads_its_own_local_date_west_of_utc() -> None:
    """The mirror of the weekday case, and the direction that bites: it is still July there.

    At 2026-08-01T02:00Z it is 2026-07-31T19:00 in Los Angeles, so a 31st-of-the-month rule at
    21:00 fires in two hours. Reading the UTC date instead would see August, find its 31st, and
    push the reminder a full month out.
    """
    rule = CalendarRule(hour=21, minute=0, on=MonthDays(days=frozenset({MAX_MONTH_DAY})))
    after = _utc(2026, 8, 1, 2, 0)
    assert after.astimezone(_LOS_ANGELES.tz).day == MAX_MONTH_DAY  # local July 31, UTC August 1
    assert next_calendar_due(rule, after, _LOS_ANGELES) == _utc(2026, 8, 1, 4, 0)


def test_a_month_day_rule_holds_its_wall_time_across_a_transition() -> None:
    """Clamping and the daylight-saving policy compose: both occurrences read 09:00 local."""
    rule = CalendarRule(hour=9, minute=0, on=MonthDays(days=frozenset({29})))
    february = next_calendar_due(rule, _utc(2026, 2, 1, 0, 0), _BUCHAREST)
    assert february is not None
    assert _BUCHAREST.render(february) == "2026-02-28T09:00:00+02:00"  # clamped, winter offset
    march = next_calendar_due(rule, february, _BUCHAREST)
    assert march is not None
    assert _BUCHAREST.render(march) == "2026-03-29T09:00:00+03:00"  # summer offset, same wall time


def test_a_month_day_occurrence_inside_a_spring_forward_gap_fires_just_past_the_gap() -> None:
    """The gap policy is inherited, not re-invented: identical to the weekday rule's."""
    rule = CalendarRule(hour=3, minute=30, on=MonthDays(days=frozenset({29})))
    due = next_calendar_due(rule, _utc(2026, 3, 20, 12, 0), _BUCHAREST)
    assert due is not None
    assert _BUCHAREST.render(due) == "2026-03-29T04:30:00+03:00"


def test_a_month_day_occurrence_past_the_representable_maximum_ends_the_recurrence() -> None:
    """The monthly fallback overflows exactly as the weekly one does, and ends the same way."""
    rule = CalendarRule(hour=23, minute=30, on=MonthDays(days=frozenset({MAX_MONTH_DAY})))
    assert next_calendar_due(rule, _utc(9999, 12, 31, 23, 59), UTC_DISPLAY) is None
