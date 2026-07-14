"""The display timezone model-facing schedule datetimes render in (ADR-0025 display addendum)."""

from dataclasses import dataclass
from datetime import UTC, datetime, tzinfo

UTC_ZONE_NAME = "UTC"


@dataclass(frozen=True, slots=True)
class DisplayZone:
    """One timezone, plus the label the model reads for it in a tool spec."""

    name: str
    tz: tzinfo

    def render(self, moment: datetime) -> str:
        """The one canonical rendering for specs, creation results, and listing lines."""
        return moment.astimezone(UTC).astimezone(self.tz).isoformat(timespec="seconds")

    def resolve(self, naive: datetime) -> datetime:
        """Read a naive wall time as this zone's local time, as a UTC instant (the fold policy)."""
        return naive.replace(tzinfo=self.tz).astimezone(UTC)


UTC_DISPLAY = DisplayZone(name=UTC_ZONE_NAME, tz=UTC)
"""The v1 contract as a value: what every deployment renders until ``CORTEX_SCHEDULE_TZ`` says
otherwise."""
