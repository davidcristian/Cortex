"""Scheduling configuration (ADR-0025): env-driven, root-read only.

Its own module per the ``config_subagents.py`` split precedent (``config.py`` is at its
line-cap budget); same rules apply. It is read exclusively by the composition root, everything below
the edge receives plain values. Scheduling is off by default so CI and the no-service dev
loop run schedule-free with the turn path byte-identical (every capability's posture).
"""

from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from cortex_core import UTC_DISPLAY, UTC_ZONE_NAME, DisplayZone

ScheduleBackendName = Literal["none", "redis"]


def _resolve(name: str) -> DisplayZone:
    """An IANA key as the core's injectable value; this is the edge's tz-database lookup.

    ``UTC`` short-circuits to the stdlib constant, so the default deployment resolves without
    consulting a tz database at all (an image shipped without one still boots and renders).
    """
    if name == UTC_ZONE_NAME:
        return UTC_DISPLAY
    return DisplayZone(name=name, tz=ZoneInfo(name))


class ScheduleConfig(BaseSettings):
    """Whether schedules exist, and the ticker's pacing knobs (ADR-0025).

    ``none`` (the default) disables scheduling end to end: no store, no built-ins, no
    ticker, and the reminder pull RPCs answer benignly empty. ``redis`` stores schedules
    durably at ``CORTEX_REDIS_URL`` (the stack's append-only Redis, with the same durability
    class sessions rely on) and starts the ticker.

    ``poll_s`` is the ticker's pass interval; ``lease_s`` bounds how long a claimed fire
    may run before a crash (or overrun) makes it re-claimable. Keep it above the slowest
    expected task fire, the runbook's tuning note; ``claim_limit`` caps one pass's batch;
    ``max_active`` caps the active items ``schedule_task`` may accumulate (the creation
    bound, so an injected turn cannot plant an unbounded workload).

    ``tz`` is the IANA key every model-facing schedule datetime renders in, and the zone an
    offset-less ``at`` is read as (ADR-0025 display addendum). Storage is unaffected: due
    times stay UTC instants in the store.
    """

    model_config = SettingsConfigDict(env_prefix="CORTEX_SCHEDULE_")

    backend: ScheduleBackendName = "none"
    poll_s: float = Field(default=5.0, gt=0)
    lease_s: float = Field(default=300.0, gt=0)
    claim_limit: int = Field(default=8, gt=0)
    max_active: int = Field(default=32, gt=0)
    tz: str = UTC_ZONE_NAME

    @field_validator("tz")
    @classmethod
    def _known_zone(cls, value: str) -> str:
        """Reject an unknown key at boot rather than at the model's first listing.

        A typo would otherwise survive as a latent failure that only surfaces once a turn
        renders a schedule, which is both far from the cause and inside a tool call.
        """
        try:
            _resolve(value)
        except (ZoneInfoNotFoundError, ValueError) as err:
            msg = f"unknown timezone {value!r}: {err}"
            raise ValueError(msg) from err
        return value

    def display_zone(self) -> DisplayZone:
        """The validated zone the builders inject into the rendering built-ins."""
        return _resolve(self.tz)
