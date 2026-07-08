"""Scheduling configuration (ADR-0025): env-driven, root-read only.

Its own module per the ``config_subagents.py`` split precedent (``config.py`` is at its
line-cap budget); same rules apply. It is read exclusively by the composition root, everything below
the edge receives plain values. Scheduling is off by default so CI and the no-service dev
loop run schedule-free with the turn path byte-identical (every capability's posture).
"""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ScheduleBackendName = Literal["none", "redis"]


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
    """

    model_config = SettingsConfigDict(env_prefix="CORTEX_SCHEDULE_")

    backend: ScheduleBackendName = "none"
    poll_s: float = Field(default=5.0, gt=0)
    lease_s: float = Field(default=300.0, gt=0)
    claim_limit: int = Field(default=8, gt=0)
    max_active: int = Field(default=32, gt=0)
