"""Resolve an IANA timezone key against the system tz database."""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from cortex_core import UTC_DISPLAY, UTC_ZONE_NAME, DisplayZone


class ZoneInfoResolver:
    """A ``ZoneResolver`` backed by the stdlib ``zoneinfo`` tz database."""

    def resolve(self, name: str) -> DisplayZone | None:
        """The zone ``name`` designates, or ``None`` when the tz database has no such key."""
        if name == UTC_ZONE_NAME:
            return UTC_DISPLAY
        try:
            return DisplayZone(name=name, tz=ZoneInfo(name))
        except (ZoneInfoNotFoundError, ValueError):
            return None


ZONEINFO_RESOLVER = ZoneInfoResolver()
"""The shared instance: the codec's decode default and the composition root's injected resolver."""
