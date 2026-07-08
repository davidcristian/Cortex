"""Scheduling configuration (ADR-0025): env-driven, root-read only."""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ScheduleBackendName = Literal["none", "redis"]


class ScheduleConfig(BaseSettings):
    """Whether schedules exist, and the ticker's pacing knobs (ADR-0025)."""

    model_config = SettingsConfigDict(env_prefix="CORTEX_SCHEDULE_")

    backend: ScheduleBackendName = "none"
    poll_s: float = Field(default=5.0, gt=0)
    lease_s: float = Field(default=300.0, gt=0)
    claim_limit: int = Field(default=8, gt=0)
    max_active: int = Field(default=32, gt=0)
