"""CalendarRule and the wall-clock occurrence math (ADR-0025 calendar addendum).

Like ``test_schedule_time.py``, the daylight-saving cases run against a real ``ZoneInfo``
rather than a fixed-offset fake: a rule that "follows the wall clock" is only meaningfully
tested in a zone that actually transitions, and the whole point of the shape is the behavior
an interval gets wrong there. Europe/Bucharest is +02:00 in winter and +03:00 in summer, with
both 2026 transitions landing on a 03:00-04:00 local window.
"""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from cortex_core import (
    UTC_DISPLAY,
    CalendarRule,
    DisplayZone,
    MonthDay,
    MonthDays,
    Weekdays,
    YearDays,
)
from cortex_core.schedule_calendar import next_calendar_due
from cortex_core.schedule_selectors import DAILY, DAY_NAMES, EVERY_DAY, MAX_MONTH_DAY

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
    """The direction that actually matters: west of UTC, the UTC date is already *tomorrow*.

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
    """``None`` matches ``next_due``: ending the recurrence is better than a re-arm that could
    never persist."""
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
    """The mirror of the weekday case, and the direction that matters: it is still July there.

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
    """The gap policy is inherited rather than re-invented: it matches the weekday rule's."""
    rule = CalendarRule(hour=3, minute=30, on=MonthDays(days=frozenset({29})))
    due = next_calendar_due(rule, _utc(2026, 3, 20, 12, 0), _BUCHAREST)
    assert due is not None
    assert _BUCHAREST.render(due) == "2026-03-29T04:30:00+03:00"


def test_a_month_day_occurrence_past_the_representable_maximum_ends_the_recurrence() -> None:
    """The monthly fallback overflows exactly as the weekly one does, and ends the same way."""
    rule = CalendarRule(hour=23, minute=30, on=MonthDays(days=frozenset({MAX_MONTH_DAY})))
    assert next_calendar_due(rule, _utc(9999, 12, 31, 23, 59), UTC_DISPLAY) is None


def test_a_month_day_rejects_a_month_off_the_calendar() -> None:
    for month in (0, len(DAY_NAMES) + 6):  # 0 and 13: months are 1..12
        with pytest.raises(ValueError, match=r"MonthDay\.month"):
            MonthDay(month=month, day=1)


@pytest.mark.parametrize(("month", "day"), [(1, 0), (1, 32), (2, 30), (4, 31)])
def test_a_month_day_rejects_a_day_that_month_never_has(month: int, day: int) -> None:
    """Bounded by the month's leap-year length, so 30 February is a mistake rather than a
    request to clamp.

    April really has no 31st either, unlike the monthly selector's ``[31]``, which means "the
    last day of every month" precisely because it spans months. A yearly date names one month,
    so there is no reading of 31 April that is not an error worth correcting.
    """
    with pytest.raises(ValueError, match=r"MonthDay\.day"):
        MonthDay(month=month, day=day)


def test_a_month_day_accepts_the_leap_day_and_resolves_it_per_year() -> None:
    """29 February is a real date, so it constructs; which instant it names is the year's call."""
    leap_day = MonthDay(month=2, day=29)
    assert leap_day.resolve(2028) == date(2028, 2, 29)  # a leap year reaches it
    assert leap_day.resolve(2026) == date(2026, 2, 28)  # a common year clamps back one day


def test_dates_sort_chronologically_within_the_year() -> None:
    """Month-first ordering is what the walk and the listing both rely on, each reading the
    dates in sorted order."""
    assert sorted({MonthDay(month=12, day=25), MonthDay(month=1, day=1)}) == [
        MonthDay(month=1, day=1),
        MonthDay(month=12, day=25),
    ]


def test_a_year_date_selector_rejects_an_empty_date_set() -> None:
    """Empty would make the occurrence search unbounded, exactly as for its two siblings."""
    with pytest.raises(ValueError, match="YearDays"):
        YearDays(days=frozenset[MonthDay]())


def test_describe_names_year_dates_in_calendar_order() -> None:
    rule = CalendarRule(
        hour=9, minute=0, on=YearDays(days=frozenset({MonthDay(12, 25), MonthDay(1, 1)}))
    )
    assert rule.describe() == "every year on 1 jan, 25 dec at 09:00"


def test_todays_year_date_occurrence_is_next_when_its_wall_time_is_still_ahead() -> None:
    rule = CalendarRule(hour=9, minute=0, on=YearDays(days=frozenset({MonthDay(7, 20)})))
    assert next_calendar_due(rule, _utc(2026, 7, 20, 6, 0), UTC_DISPLAY) == _utc(2026, 7, 20, 9)


def test_the_year_search_moves_to_the_next_listed_date_of_the_same_year() -> None:
    rule = CalendarRule(
        hour=9, minute=0, on=YearDays(days=frozenset({MonthDay(3, 3), MonthDay(12, 25)}))
    )
    assert next_calendar_due(rule, _utc(2026, 7, 2, 12, 0), UTC_DISPLAY) == _utc(2026, 12, 25, 9)


def test_the_year_search_wraps_into_the_following_year() -> None:
    """A December rule asked after it has passed takes the fallback, next year's first date."""
    rule = CalendarRule(hour=9, minute=0, on=YearDays(days=frozenset({MonthDay(12, 25)})))
    assert next_calendar_due(rule, _utc(2026, 12, 26, 12, 0), UTC_DISPLAY) == _utc(2027, 12, 25, 9)


def test_a_year_date_occurrence_is_strictly_after_so_firing_does_not_re_arm_in_place() -> None:
    """The annual case of the property every selector owes: a fire lands on the NEXT year."""
    rule = CalendarRule(hour=9, minute=0, on=YearDays(days=frozenset({MonthDay(12, 25)})))
    fired_at = _utc(2026, 12, 25, 9, 0)
    assert next_calendar_due(rule, fired_at, UTC_DISPLAY) == _utc(2027, 12, 25, 9)


def test_an_annual_rule_does_not_drift_across_a_leap_year() -> None:
    """The headline property, and the reason a 365 day interval is the wrong shape here.

    Four consecutive occurrences of a 25 December rule stay on 25 December, spanning the 2028
    leap year. An ``every=timedelta(days=365)`` item would have walked back to 24 December
    after 2028 and kept walking, a day per leap year, silently.
    """
    rule = CalendarRule(hour=9, minute=0, on=YearDays(days=frozenset({MonthDay(12, 25)})))
    due = _utc(2026, 12, 25, 9)
    for year in (2027, 2028, 2029, 2030):
        nxt = next_calendar_due(rule, due, UTC_DISPLAY)
        assert nxt == _utc(year, 12, 25, 9)
        assert nxt is not None
        due = nxt


def test_the_leap_day_clamps_to_february_28_in_a_common_year() -> None:
    """The clamp policy inherited from the monthly selector: it fires every year, never one in
    four. A 29 February reminder that arrives on the 28th beats one that silently does not."""
    rule = CalendarRule(hour=9, minute=0, on=YearDays(days=frozenset({MonthDay(2, 29)})))
    assert next_calendar_due(rule, _utc(2026, 1, 10, 12, 0), UTC_DISPLAY) == _utc(2026, 2, 28, 9)
    assert next_calendar_due(rule, _utc(2028, 1, 10, 12, 0), UTC_DISPLAY) == _utc(2028, 2, 29, 9)


def test_dates_that_clamp_together_fire_once_not_twice() -> None:
    """28 and 29 February collide in a common year; the walk resolves dates, so it fires once."""
    rule = CalendarRule(
        hour=9, minute=0, on=YearDays(days=frozenset({MonthDay(2, 28), MonthDay(2, 29)}))
    )
    february = next_calendar_due(rule, _utc(2026, 1, 10, 12, 0), UTC_DISPLAY)
    assert february is not None
    assert february == _utc(2026, 2, 28, 9)
    # The next occurrence leaves the year entirely rather than repeating the collided date.
    assert next_calendar_due(rule, february, UTC_DISPLAY) == _utc(2027, 2, 28, 9)
    # A leap year separates them again, so the same rule fires on both days there.
    leap = next_calendar_due(rule, _utc(2028, 1, 10, 12, 0), UTC_DISPLAY)
    assert leap == _utc(2028, 2, 28, 9)
    assert next_calendar_due(rule, _utc(2028, 2, 28, 9), UTC_DISPLAY) == _utc(2028, 2, 29, 9)


def test_a_year_date_rule_reads_its_own_local_date_west_of_utc() -> None:
    """The direction that matters, for the annual window: it is still 25 December there.

    At 2026-12-26T02:00Z it is 2026-12-25T18:00 in Los Angeles, so a 25 December 21:00 rule
    fires in three hours. Reading the UTC date instead would see the 26th and push the
    reminder a full YEAR out, which is the worst version of this bug the three selectors have.
    """
    rule = CalendarRule(hour=21, minute=0, on=YearDays(days=frozenset({MonthDay(12, 25)})))
    after = _utc(2026, 12, 26, 2, 0)
    assert after.astimezone(_LOS_ANGELES.tz).day == 25  # local 25 December, UTC the 26th
    assert next_calendar_due(rule, after, _LOS_ANGELES) == _utc(2026, 12, 26, 5, 0)


def test_a_year_date_rule_holds_its_wall_time_across_a_transition() -> None:
    """Two consecutive occurrences of a summer date read 09:00 local on both sides of a year."""
    rule = CalendarRule(hour=9, minute=0, on=YearDays(days=frozenset({MonthDay(7, 20)})))
    summer = next_calendar_due(rule, _utc(2026, 1, 1, 0, 0), _BUCHAREST)
    assert summer is not None
    assert _BUCHAREST.render(summer) == "2026-07-20T09:00:00+03:00"
    assert next_calendar_due(rule, summer, _BUCHAREST) == _utc(2027, 7, 20, 6, 0)


def test_a_year_date_occurrence_inside_a_spring_forward_gap_fires_just_past_the_gap() -> None:
    """The gap policy is inherited rather than re-invented: it matches its two siblings'."""
    rule = CalendarRule(hour=3, minute=30, on=YearDays(days=frozenset({MonthDay(3, 29)})))
    due = next_calendar_due(rule, _utc(2026, 3, 20, 12, 0), _BUCHAREST)
    assert due is not None
    assert _BUCHAREST.render(due) == "2026-03-29T04:30:00+03:00"


def test_a_year_date_occurrence_past_the_representable_maximum_ends_the_recurrence() -> None:
    """The annual fallback reaches year 10000, which no date holds; the recurrence ends."""
    rule = CalendarRule(hour=23, minute=30, on=YearDays(days=frozenset({MonthDay(12, 31)})))
    assert next_calendar_due(rule, _utc(9999, 12, 31, 23, 59), UTC_DISPLAY) is None


# --- Per-rule timezone (ADR-0025 per-rule addendum) ---


def test_describe_names_a_per_rule_zone() -> None:
    """A rule that carries a zone states it, so a bare wall time is never ambiguous."""
    plain = CalendarRule(hour=9, minute=0)
    zoned = CalendarRule(hour=9, minute=0, zone=_LOS_ANGELES)
    assert plain.describe() == "every day at 09:00"
    assert zoned.describe() == "every day at 09:00 (America/Los_Angeles)"


def test_a_rule_with_its_own_zone_fires_at_that_zones_wall_clock() -> None:
    """The rule's own zone governs, not the deployment zone the ticker passes.

    At noon UTC on 12 July the Los Angeles wall clock reads 05:00, so a daily 09:00 rule in that
    zone still fires later the same UTC day (09:00-07:00 = 16:00 UTC), where a zone-less rule read
    against UTC would already have passed 09:00 and land on the 13th.
    """
    after = _utc(2026, 7, 12, 12, 0)
    zoned = CalendarRule(hour=9, minute=0, zone=_LOS_ANGELES)
    # The deployment zone is UTC, and it is ignored because the rule named its own.
    assert next_calendar_due(zoned, after, UTC_DISPLAY) == _utc(2026, 7, 12, 16, 0)
    # Identical to passing that zone as the deployment default for a zone-less rule.
    plain = CalendarRule(hour=9, minute=0)
    assert next_calendar_due(zoned, after, UTC_DISPLAY) == next_calendar_due(
        plain, after, _LOS_ANGELES
    )
    # A zone-less rule under a UTC deployment lands on the next day instead.
    assert next_calendar_due(plain, after, UTC_DISPLAY) == _utc(2026, 7, 13, 9, 0)


def test_a_per_rule_zone_follows_daylight_saving_independently() -> None:
    """The rule's zone drives the fold, so a per-zone rule keeps its wall time across a DST edge
    that the deployment zone does not share."""
    rule = CalendarRule(hour=3, minute=30, zone=_BUCHAREST)
    # Just after 28 March's occurrence, so the next daily fire is 29 March, inside the gap.
    due = next_calendar_due(rule, _utc(2026, 3, 28, 12, 0), UTC_DISPLAY)
    assert due is not None
    # Bucharest springs forward over 03:30 on 29 March 2026, so it fires just past the gap, even
    # though the deployment zone (UTC) has no such transition.
    assert _BUCHAREST.render(due) == "2026-03-29T04:30:00+03:00"
