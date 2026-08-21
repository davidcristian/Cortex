"""Scheduling configuration (ADR-0025): env-driven, root-read only."""

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from cortex_core import UTC_ZONE_NAME, DisplayZone
from cortex_session import ZONEINFO_RESOLVER

ScheduleBackendName = Literal["none", "redis"]

# Whether a deployment gets a durable schedule store when nothing says otherwise. Named for the
# reason the zone beside it already was: the base compose file ships the same answer as a
# substitution default, and a scan can only hold that to a declaration it can read.
DEFAULT_SCHEDULE_BACKEND: ScheduleBackendName = "none"


def _resolve(name: str) -> DisplayZone:
    """An IANA key as the core's injectable value, via the shared ``zoneinfo`` resolver."""
    zone = ZONEINFO_RESOLVER.resolve(name)
    if zone is None:
        msg = f"unknown timezone {name!r}"
        raise ValueError(msg)
    return zone


class ScheduleConfig(BaseSettings):
    """Whether schedules exist, and the ticker's pacing knobs (ADR-0025)."""

    model_config = SettingsConfigDict(env_prefix="CORTEX_SCHEDULE_")

    backend: ScheduleBackendName = DEFAULT_SCHEDULE_BACKEND
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
        except ValueError as err:
            raise ValueError(str(err)) from err
        return value

    def display_zone(self) -> DisplayZone:
        """The validated zone the builders inject into the rendering built-ins."""
        return _resolve(self.tz)
