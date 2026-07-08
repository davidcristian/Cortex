"""ScheduleConfig: defaults, env names, and the constructor-beats-env rule (ADR-0025)."""

import pytest
from pydantic import ValidationError

from cortex_orchestrator import ScheduleConfig


def test_defaults_are_schedule_free(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "CORTEX_SCHEDULE_BACKEND",
        "CORTEX_SCHEDULE_POLL_S",
        "CORTEX_SCHEDULE_LEASE_S",
        "CORTEX_SCHEDULE_CLAIM_LIMIT",
        "CORTEX_SCHEDULE_MAX_ACTIVE",
    ):
        monkeypatch.delenv(name, raising=False)
    config = ScheduleConfig()
    assert config.backend == "none"
    assert config.poll_s == 5.0
    assert config.lease_s == 300.0
    assert config.claim_limit == 8
    assert config.max_active == 32


def test_env_names_flow_through(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_SCHEDULE_BACKEND", "redis")
    monkeypatch.setenv("CORTEX_SCHEDULE_POLL_S", "2.5")
    monkeypatch.setenv("CORTEX_SCHEDULE_LEASE_S", "60")
    monkeypatch.setenv("CORTEX_SCHEDULE_CLAIM_LIMIT", "4")
    monkeypatch.setenv("CORTEX_SCHEDULE_MAX_ACTIVE", "10")
    config = ScheduleConfig()
    assert config.backend == "redis"
    assert config.poll_s == 2.5
    assert config.lease_s == 60.0
    assert config.claim_limit == 4
    assert config.max_active == 10


def test_constructor_beats_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_SCHEDULE_BACKEND", "redis")
    assert ScheduleConfig(backend="none").backend == "none"


@pytest.mark.parametrize("field", ["poll_s", "lease_s", "claim_limit", "max_active"])
def test_pacing_knobs_must_be_positive(field: str) -> None:
    with pytest.raises(ValidationError):
        ScheduleConfig(**{field: 0})  # type: ignore[arg-type]
