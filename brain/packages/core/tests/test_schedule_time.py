from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from cortex_core import (
    UTC_DISPLAY,
    UTC_ONLY_RESOLVER,
    UTC_ZONE_CONTEXT,
    UTC_ZONE_NAME,
    DisplayZone,
    ZoneContext,
)

# +02:00 in winter and +03:00 in summer, with both transitions inside 2026.
_BUCHAREST = DisplayZone(name="Europe/Bucharest", tz=ZoneInfo("Europe/Bucharest"))


def _naive(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    """A wall time with no zone, which is the input the fold policy reads."""
    return datetime(year, month, day, hour, minute)  # noqa: DTZ001 - naive is the subject


def test_the_default_zone_is_utc() -> None:
    assert UTC_DISPLAY.name == UTC_ZONE_NAME
    assert UTC_DISPLAY.tz is UTC


def test_utc_rendering_is_unchanged_from_the_utc_only_v1() -> None:
    moment = datetime(2026, 7, 12, 18, 0, 0, tzinfo=UTC)
    assert UTC_DISPLAY.render(moment) == "2026-07-12T18:00:00+00:00"


def test_rendering_converts_the_instant_and_carries_the_offset() -> None:
    moment = datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)
    assert _BUCHAREST.render(moment) == "2026-07-12T15:00:00+03:00"


def test_rendering_accepts_an_instant_from_any_zone() -> None:
    moment = datetime(2026, 7, 12, 8, 0, 0, tzinfo=timezone(timedelta(hours=-4)))
    assert _BUCHAREST.render(moment) == "2026-07-12T15:00:00+03:00"


def test_seconds_precision_drops_microseconds() -> None:
    moment = datetime(2026, 7, 12, 18, 0, 0, 123456, tzinfo=UTC)
    assert UTC_DISPLAY.render(moment) == "2026-07-12T18:00:00+00:00"


def test_resolve_reads_a_naive_wall_time_as_this_zone() -> None:
    resolved = _BUCHAREST.resolve(_naive(2026, 7, 12, 15, 0))
    assert resolved == datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)
    assert resolved.utcoffset() == timedelta(0)
    assert _BUCHAREST.render(resolved) == "2026-07-12T15:00:00+03:00"


def test_resolve_under_utc_is_the_v1_reading() -> None:
    resolved = UTC_DISPLAY.resolve(_naive(2026, 7, 12, 18, 0))
    assert resolved == datetime(2026, 7, 12, 18, 0, 0, tzinfo=UTC)


def test_an_ambiguous_wall_time_takes_the_earlier_offset() -> None:
    resolved = _BUCHAREST.resolve(_naive(2026, 10, 25, 3, 30))
    assert resolved == datetime(2026, 10, 25, 0, 30, 0, tzinfo=UTC)
    assert datetime(2026, 10, 25, 3, 30, fold=1, tzinfo=_BUCHAREST.tz).astimezone(UTC) == datetime(
        2026, 10, 25, 1, 30, 0, tzinfo=UTC
    )


def test_a_nonexistent_wall_time_uses_the_pre_transition_offset() -> None:
    resolved = _BUCHAREST.resolve(_naive(2026, 3, 29, 3, 30))
    assert resolved == datetime(2026, 3, 29, 1, 30, 0, tzinfo=UTC)
    assert _BUCHAREST.render(resolved) == "2026-03-29T04:30:00+03:00"


def test_rendering_never_prints_a_wall_time_that_does_not_exist() -> None:
    gap_local = datetime(2026, 3, 29, 3, 30, 0, tzinfo=_BUCHAREST.tz)
    assert _BUCHAREST.render(gap_local) == "2026-03-29T04:30:00+03:00"


def test_the_zone_is_a_frozen_value() -> None:
    assert DisplayZone(name="UTC", tz=UTC) == UTC_DISPLAY
    assert hash(DisplayZone(name="UTC", tz=UTC)) == hash(UTC_DISPLAY)


def test_the_utc_only_resolver_knows_only_utc() -> None:
    assert UTC_ONLY_RESOLVER.resolve(UTC_ZONE_NAME) is UTC_DISPLAY
    assert UTC_ONLY_RESOLVER.resolve("America/New_York") is None


def test_the_default_zone_context_is_utc_render_and_utc_only_resolution() -> None:
    assert UTC_ZONE_CONTEXT.default is UTC_DISPLAY
    assert UTC_ZONE_CONTEXT.resolver is UTC_ONLY_RESOLVER
    assert ZoneContext() == UTC_ZONE_CONTEXT


def test_a_zone_context_carries_its_own_default_and_resolver() -> None:
    zone = DisplayZone(name="Europe/Bucharest", tz=ZoneInfo("Europe/Bucharest"))
    context = ZoneContext(default=zone, resolver=UTC_ONLY_RESOLVER)
    assert context.default is zone
    assert context.resolver is UTC_ONLY_RESOLVER
