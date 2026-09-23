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
# Behind UTC, so its local date can be a day earlier than the UTC one.
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
    with pytest.raises(ValueError, match="CalendarRule"):
        CalendarRule(hour=hour, minute=minute)


@pytest.mark.parametrize(
    "days",
    [
        frozenset[int](),
        frozenset({7}),
    ],
)
def test_a_weekday_selector_rejects_an_unusable_day_set(days: frozenset[int]) -> None:
    with pytest.raises(ValueError, match="Weekdays"):
        Weekdays(days=days)


@pytest.mark.parametrize(
    "days",
    [
        frozenset[int](),
        frozenset({0}),
        frozenset({MAX_MONTH_DAY + 1}),
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
        (11, "11th"),
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


def test_the_occurrence_is_strictly_after_so_firing_does_not_reschedule_in_place() -> None:
    rule = CalendarRule(hour=9, minute=0)
    fired_at = _utc(2026, 7, 20, 9, 0)
    assert next_calendar_due(rule, fired_at, UTC_DISPLAY) == _utc(2026, 7, 21, 9)


def test_a_restricted_day_set_skips_to_the_next_listed_weekday() -> None:
    rule = CalendarRule(hour=9, minute=0, on=Weekdays(days=_WEEKDAYS))
    assert next_calendar_due(rule, _utc(2026, 7, 18, 12, 0), UTC_DISPLAY) == _utc(2026, 7, 20, 9)


def test_the_search_wraps_into_the_following_week() -> None:
    rule = CalendarRule(hour=9, minute=0, on=Weekdays(days=frozenset({_MON})))
    monday_afternoon = _utc(2026, 7, 20, 15, 0)
    assert monday_afternoon.weekday() == _MON
    assert next_calendar_due(rule, monday_afternoon, UTC_DISPLAY) == _utc(2026, 7, 27, 9)


def test_the_local_date_drives_the_search_not_the_utc_date() -> None:
    rule = CalendarRule(hour=9, minute=0)
    assert next_calendar_due(rule, _utc(2026, 7, 20, 23, 0), _BUCHAREST) == _utc(2026, 7, 21, 6)


def test_a_zone_behind_utc_reads_its_own_weekday_not_the_utc_one() -> None:
    rule = CalendarRule(hour=21, minute=0, on=Weekdays(days=frozenset({_MON})))
    after = _utc(2026, 7, 21, 2, 0)
    assert after.astimezone(_LOS_ANGELES.tz).weekday() == _MON
    assert next_calendar_due(rule, after, _LOS_ANGELES) == _utc(2026, 7, 21, 4, 0)  # local Monday


def test_the_wall_time_holds_across_a_spring_forward_transition() -> None:
    rule = CalendarRule(hour=9, minute=0)
    before = _utc(2026, 3, 28, 7, 0)
    assert _BUCHAREST.render(before) == "2026-03-28T09:00:00+02:00"
    after = next_calendar_due(rule, before, _BUCHAREST)
    assert after is not None
    assert after == _utc(2026, 3, 29, 6, 0)  # 23 hours later: the clocks moved forward an hour
    assert _BUCHAREST.render(after) == "2026-03-29T09:00:00+03:00"


def test_the_wall_time_holds_across_a_fall_back_transition() -> None:
    rule = CalendarRule(hour=9, minute=0)
    before = _utc(2026, 10, 24, 6, 0)
    after = next_calendar_due(rule, before, _BUCHAREST)
    assert after is not None
    assert after == _utc(2026, 10, 25, 7, 0)  # 25 hours later: the clocks moved back an hour
    assert _BUCHAREST.render(after) == "2026-10-25T09:00:00+02:00"


def test_an_occurrence_inside_a_spring_forward_gap_fires_just_past_the_gap() -> None:
    rule = CalendarRule(hour=3, minute=30)
    due = next_calendar_due(rule, _utc(2026, 3, 28, 12, 0), _BUCHAREST)
    assert due is not None
    assert due == _utc(2026, 3, 29, 1, 30)
    assert _BUCHAREST.render(due) == "2026-03-29T04:30:00+03:00"


def test_a_repeated_wall_hour_fires_once_not_twice() -> None:
    rule = CalendarRule(hour=3, minute=30)
    first = next_calendar_due(rule, _utc(2026, 10, 25, 0, 0), _BUCHAREST)
    assert first is not None
    assert first == _utc(2026, 10, 25, 0, 30)  # 03:30+03:00, the earlier of the two readings
    assert next_calendar_due(rule, first, _BUCHAREST) == _utc(2026, 10, 26, 1, 30)


def test_an_occurrence_past_the_representable_maximum_ends_the_recurrence() -> None:
    rule = CalendarRule(hour=23, minute=30)
    assert next_calendar_due(rule, _utc(9999, 12, 31, 23, 59), UTC_DISPLAY) is None


def test_todays_month_day_occurrence_is_next_when_its_wall_time_is_still_ahead() -> None:
    rule = CalendarRule(hour=9, minute=0, on=MonthDays(days=frozenset({20})))
    assert next_calendar_due(rule, _utc(2026, 7, 20, 6, 0), UTC_DISPLAY) == _utc(2026, 7, 20, 9)


def test_the_month_search_moves_to_the_next_listed_day_of_the_same_month() -> None:
    rule = CalendarRule(hour=9, minute=0, on=MonthDays(days=frozenset({1, 15})))
    assert next_calendar_due(rule, _utc(2026, 7, 2, 12, 0), UTC_DISPLAY) == _utc(2026, 7, 15, 9)


def test_the_month_search_wraps_into_the_following_month() -> None:
    rule = CalendarRule(hour=9, minute=0, on=MonthDays(days=frozenset({1})))
    assert next_calendar_due(rule, _utc(2026, 7, 15, 12, 0), UTC_DISPLAY) == _utc(2026, 8, 1, 9)


def test_the_month_search_wraps_across_a_year_boundary() -> None:
    rule = CalendarRule(hour=9, minute=0, on=MonthDays(days=frozenset({1})))
    assert next_calendar_due(rule, _utc(2026, 12, 15, 12, 0), UTC_DISPLAY) == _utc(2027, 1, 1, 9)


def test_a_month_day_occurrence_is_strictly_after_so_firing_does_not_reschedule_in_place() -> None:
    rule = CalendarRule(hour=9, minute=0, on=MonthDays(days=frozenset({20})))
    fired_at = _utc(2026, 7, 20, 9, 0)
    assert next_calendar_due(rule, fired_at, UTC_DISPLAY) == _utc(2026, 8, 20, 9)


def test_a_day_a_short_month_lacks_fires_on_that_months_last_day() -> None:
    rule = CalendarRule(hour=9, minute=0, on=MonthDays(days=frozenset({MAX_MONTH_DAY})))
    assert next_calendar_due(rule, _utc(2026, 2, 10, 12, 0), UTC_DISPLAY) == _utc(2026, 2, 28, 9)
    assert next_calendar_due(rule, _utc(2026, 4, 10, 12, 0), UTC_DISPLAY) == _utc(2026, 4, 30, 9)


def test_the_clamp_follows_the_leap_year_rather_than_a_fixed_february() -> None:
    rule = CalendarRule(hour=9, minute=0, on=MonthDays(days=frozenset({MAX_MONTH_DAY})))
    assert next_calendar_due(rule, _utc(2028, 2, 10, 12, 0), UTC_DISPLAY) == _utc(2028, 2, 29, 9)


def test_days_that_clamp_together_fire_once_not_twice() -> None:
    rule = CalendarRule(hour=9, minute=0, on=MonthDays(days=frozenset({30, MAX_MONTH_DAY})))
    february = next_calendar_due(rule, _utc(2026, 2, 10, 12, 0), UTC_DISPLAY)
    assert february is not None
    assert february == _utc(2026, 2, 28, 9)
    assert next_calendar_due(rule, february, UTC_DISPLAY) == _utc(2026, 3, 30, 9)


def test_a_month_day_rule_reads_its_own_local_date_west_of_utc() -> None:
    rule = CalendarRule(hour=21, minute=0, on=MonthDays(days=frozenset({MAX_MONTH_DAY})))
    after = _utc(2026, 8, 1, 2, 0)
    assert after.astimezone(_LOS_ANGELES.tz).day == MAX_MONTH_DAY
    assert next_calendar_due(rule, after, _LOS_ANGELES) == _utc(2026, 8, 1, 4, 0)


def test_a_month_day_rule_holds_its_wall_time_across_a_transition() -> None:
    rule = CalendarRule(hour=9, minute=0, on=MonthDays(days=frozenset({29})))
    february = next_calendar_due(rule, _utc(2026, 2, 1, 0, 0), _BUCHAREST)
    assert february is not None
    assert _BUCHAREST.render(february) == "2026-02-28T09:00:00+02:00"
    march = next_calendar_due(rule, february, _BUCHAREST)
    assert march is not None
    assert _BUCHAREST.render(march) == "2026-03-29T09:00:00+03:00"


def test_a_month_day_occurrence_inside_a_spring_forward_gap_fires_just_past_the_gap() -> None:
    rule = CalendarRule(hour=3, minute=30, on=MonthDays(days=frozenset({29})))
    due = next_calendar_due(rule, _utc(2026, 3, 20, 12, 0), _BUCHAREST)
    assert due is not None
    assert _BUCHAREST.render(due) == "2026-03-29T04:30:00+03:00"


def test_a_month_day_occurrence_past_the_representable_maximum_ends_the_recurrence() -> None:
    rule = CalendarRule(hour=23, minute=30, on=MonthDays(days=frozenset({MAX_MONTH_DAY})))
    assert next_calendar_due(rule, _utc(9999, 12, 31, 23, 59), UTC_DISPLAY) is None


def test_a_month_day_rejects_a_month_off_the_calendar() -> None:
    for month in (0, len(DAY_NAMES) + 6):
        with pytest.raises(ValueError, match=r"MonthDay\.month"):
            MonthDay(month=month, day=1)


@pytest.mark.parametrize(("month", "day"), [(1, 0), (1, 32), (2, 30), (4, 31)])
def test_a_month_day_rejects_a_day_that_month_never_has(month: int, day: int) -> None:
    with pytest.raises(ValueError, match=r"MonthDay\.day"):
        MonthDay(month=month, day=day)


def test_a_month_day_accepts_the_leap_day_and_resolves_it_per_year() -> None:
    leap_day = MonthDay(month=2, day=29)
    assert leap_day.resolve(2028) == date(2028, 2, 29)
    assert leap_day.resolve(2026) == date(2026, 2, 28)


def test_dates_sort_chronologically_within_the_year() -> None:
    assert sorted({MonthDay(month=12, day=25), MonthDay(month=1, day=1)}) == [
        MonthDay(month=1, day=1),
        MonthDay(month=12, day=25),
    ]


def test_a_year_date_selector_rejects_an_empty_date_set() -> None:
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
    rule = CalendarRule(hour=9, minute=0, on=YearDays(days=frozenset({MonthDay(12, 25)})))
    assert next_calendar_due(rule, _utc(2026, 12, 26, 12, 0), UTC_DISPLAY) == _utc(2027, 12, 25, 9)


def test_a_year_date_occurrence_is_strictly_after_so_firing_does_not_reschedule_in_place() -> None:
    rule = CalendarRule(hour=9, minute=0, on=YearDays(days=frozenset({MonthDay(12, 25)})))
    fired_at = _utc(2026, 12, 25, 9, 0)
    assert next_calendar_due(rule, fired_at, UTC_DISPLAY) == _utc(2027, 12, 25, 9)


def test_an_annual_rule_does_not_drift_across_a_leap_year() -> None:
    rule = CalendarRule(hour=9, minute=0, on=YearDays(days=frozenset({MonthDay(12, 25)})))
    due = _utc(2026, 12, 25, 9)
    for year in (2027, 2028, 2029, 2030):
        nxt = next_calendar_due(rule, due, UTC_DISPLAY)
        assert nxt == _utc(year, 12, 25, 9)
        assert nxt is not None
        due = nxt


def test_the_leap_day_clamps_to_february_28_in_a_common_year() -> None:
    rule = CalendarRule(hour=9, minute=0, on=YearDays(days=frozenset({MonthDay(2, 29)})))
    assert next_calendar_due(rule, _utc(2026, 1, 10, 12, 0), UTC_DISPLAY) == _utc(2026, 2, 28, 9)
    assert next_calendar_due(rule, _utc(2028, 1, 10, 12, 0), UTC_DISPLAY) == _utc(2028, 2, 29, 9)


def test_dates_that_clamp_together_fire_once_not_twice() -> None:
    rule = CalendarRule(
        hour=9, minute=0, on=YearDays(days=frozenset({MonthDay(2, 28), MonthDay(2, 29)}))
    )
    february = next_calendar_due(rule, _utc(2026, 1, 10, 12, 0), UTC_DISPLAY)
    assert february is not None
    assert february == _utc(2026, 2, 28, 9)
    assert next_calendar_due(rule, february, UTC_DISPLAY) == _utc(2027, 2, 28, 9)
    leap = next_calendar_due(rule, _utc(2028, 1, 10, 12, 0), UTC_DISPLAY)
    assert leap == _utc(2028, 2, 28, 9)
    assert next_calendar_due(rule, _utc(2028, 2, 28, 9), UTC_DISPLAY) == _utc(2028, 2, 29, 9)


def test_a_year_date_rule_reads_its_own_local_date_west_of_utc() -> None:
    rule = CalendarRule(hour=21, minute=0, on=YearDays(days=frozenset({MonthDay(12, 25)})))
    after = _utc(2026, 12, 26, 2, 0)
    assert after.astimezone(_LOS_ANGELES.tz).day == 25
    assert next_calendar_due(rule, after, _LOS_ANGELES) == _utc(2026, 12, 26, 5, 0)


def test_a_year_date_rule_holds_its_wall_time_across_a_transition() -> None:
    rule = CalendarRule(hour=9, minute=0, on=YearDays(days=frozenset({MonthDay(7, 20)})))
    summer = next_calendar_due(rule, _utc(2026, 1, 1, 0, 0), _BUCHAREST)
    assert summer is not None
    assert _BUCHAREST.render(summer) == "2026-07-20T09:00:00+03:00"
    assert next_calendar_due(rule, summer, _BUCHAREST) == _utc(2027, 7, 20, 6, 0)


def test_a_year_date_occurrence_inside_a_spring_forward_gap_fires_just_past_the_gap() -> None:
    rule = CalendarRule(hour=3, minute=30, on=YearDays(days=frozenset({MonthDay(3, 29)})))
    due = next_calendar_due(rule, _utc(2026, 3, 20, 12, 0), _BUCHAREST)
    assert due is not None
    assert _BUCHAREST.render(due) == "2026-03-29T04:30:00+03:00"


def test_a_year_date_occurrence_past_the_representable_maximum_ends_the_recurrence() -> None:
    rule = CalendarRule(hour=23, minute=30, on=YearDays(days=frozenset({MonthDay(12, 31)})))
    assert next_calendar_due(rule, _utc(9999, 12, 31, 23, 59), UTC_DISPLAY) is None


def test_describe_names_a_per_rule_zone() -> None:
    plain = CalendarRule(hour=9, minute=0)
    zoned = CalendarRule(hour=9, minute=0, zone=_LOS_ANGELES)
    assert plain.describe() == "every day at 09:00"
    assert zoned.describe() == "every day at 09:00 (America/Los_Angeles)"


def test_a_rule_with_its_own_zone_fires_at_that_zones_wall_clock() -> None:
    after = _utc(2026, 7, 12, 12, 0)
    zoned = CalendarRule(hour=9, minute=0, zone=_LOS_ANGELES)
    assert next_calendar_due(zoned, after, UTC_DISPLAY) == _utc(2026, 7, 12, 16, 0)
    plain = CalendarRule(hour=9, minute=0)
    assert next_calendar_due(zoned, after, UTC_DISPLAY) == next_calendar_due(
        plain, after, _LOS_ANGELES
    )
    assert next_calendar_due(plain, after, UTC_DISPLAY) == _utc(2026, 7, 13, 9, 0)


def test_a_per_rule_zone_follows_daylight_saving_independently() -> None:
    rule = CalendarRule(hour=3, minute=30, zone=_BUCHAREST)
    due = next_calendar_due(rule, _utc(2026, 3, 28, 12, 0), UTC_DISPLAY)
    assert due is not None
    assert _BUCHAREST.render(due) == "2026-03-29T04:30:00+03:00"
