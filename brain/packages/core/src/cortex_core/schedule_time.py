"""The display timezone model-facing schedule datetimes render in (ADR-0025 display addendum)."""

from dataclasses import dataclass
from datetime import UTC, datetime, tzinfo
from typing import Protocol

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


class ZoneResolver(Protocol):
    """Turn an IANA key into a ``DisplayZone``, or ``None`` when the key names no known zone."""

    def resolve(self, name: str) -> DisplayZone | None: ...


class _UtcOnlyResolver:
    """The core default: it knows only ``UTC``, since every other key reads the tz database."""

    def resolve(self, name: str) -> DisplayZone | None:
        return UTC_DISPLAY if name == UTC_ZONE_NAME else None


UTC_ONLY_RESOLVER: ZoneResolver = _UtcOnlyResolver()
"""The default ``ZoneResolver``: UTC only, so the core resolves no key it cannot without the tz
database. The real, ``zoneinfo``-backed resolver is injected at the composition root."""


@dataclass(frozen=True, slots=True)
class ZoneContext:
    """The deployment display zone plus the resolver a per-rule ``in_zone`` is validated against."""

    default: DisplayZone = UTC_DISPLAY
    resolver: ZoneResolver = UTC_ONLY_RESOLVER


UTC_ZONE_CONTEXT = ZoneContext()
"""The default zone context: UTC render, UTC-only resolver (the unconfigured deployment)."""
