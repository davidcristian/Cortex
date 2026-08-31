"""ScheduleConfig: defaults, env names, and the constructor-beats-env rule (ADR-0025)."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from cortex_core import UTC_DISPLAY
from cortex_orchestrator import ScheduleConfig


def test_defaults_are_schedule_free(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "CORTEX_SCHEDULE_BACKEND",
        "CORTEX_SCHEDULE_POLL_S",
        "CORTEX_SCHEDULE_LEASE_S",
        "CORTEX_SCHEDULE_CLAIM_LIMIT",
        "CORTEX_SCHEDULE_MAX_ACTIVE",
        "CORTEX_SCHEDULE_TZ",
    ):
        monkeypatch.delenv(name, raising=False)
    config = ScheduleConfig()
    assert config.backend == "none"
    assert config.poll_s == 5.0
    assert config.lease_s == 300.0
    assert config.claim_limit == 8
    assert config.max_active == 32
    assert config.tz == "UTC"
    # The default resolves to the stdlib constant, so it needs no tz database at all.
    assert config.display_zone() is UTC_DISPLAY


def test_env_names_flow_through(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_SCHEDULE_BACKEND", "redis")
    monkeypatch.setenv("CORTEX_SCHEDULE_POLL_S", "2.5")
    monkeypatch.setenv("CORTEX_SCHEDULE_LEASE_S", "60")
    monkeypatch.setenv("CORTEX_SCHEDULE_CLAIM_LIMIT", "4")
    monkeypatch.setenv("CORTEX_SCHEDULE_MAX_ACTIVE", "10")
    monkeypatch.setenv("CORTEX_SCHEDULE_TZ", "Europe/Bucharest")
    config = ScheduleConfig()
    assert config.backend == "redis"
    assert config.poll_s == 2.5
    assert config.lease_s == 60.0
    assert config.claim_limit == 4
    assert config.max_active == 10
    assert config.tz == "Europe/Bucharest"


def test_constructor_beats_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_SCHEDULE_BACKEND", "redis")
    assert ScheduleConfig(backend="none").backend == "none"


@pytest.mark.parametrize("field", ["poll_s", "lease_s", "claim_limit", "max_active"])
def test_pacing_knobs_must_be_positive(field: str) -> None:
    with pytest.raises(ValidationError):
        ScheduleConfig(**{field: 0})  # type: ignore[arg-type]


def test_a_configured_zone_resolves_to_that_zone() -> None:
    zone = ScheduleConfig(tz="Europe/Bucharest").display_zone()
    assert zone.name == "Europe/Bucharest"
    assert zone.tz == ZoneInfo("Europe/Bucharest")
    assert zone.render(datetime(2026, 7, 12, 12, 0, tzinfo=UTC)) == "2026-07-12T15:00:00+03:00"


@pytest.mark.parametrize("bad", ["Europe/Bucarest", "not a zone", "../../etc/passwd", ""])
def test_an_unknown_zone_fails_at_boot_not_at_the_first_listing(bad: str) -> None:
    """A typo raises while the config is built, where an operator can read it, rather than inside
    a later tool call."""
    with pytest.raises(ValidationError, match="unknown timezone"):
        ScheduleConfig(tz=bad)
