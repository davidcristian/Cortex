"""Resolve an IANA timezone key against the system tz database (ADR-0025 per-rule addendum).

The core's ``ZoneResolver`` port turns a name into a ``DisplayZone`` without importing
``zoneinfo``, and this adapter is the ``zoneinfo``-backed implementation of it. It lives in the
session package because the schedule codec depends on it to
reconstruct a stored rule's zone on decode; the composition root imports the same instance to
inject into the model-facing schedule tools, so one lookup serves durable deserialization and
creation-time validation alike. ``None`` (never an exception) is the "no such zone" answer, which
each caller turns into a model correction or, at decode, a corrupt-record failure.
"""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from cortex_core import UTC_DISPLAY, UTC_ZONE_NAME, DisplayZone


class ZoneInfoResolver:
    """A ``ZoneResolver`` backed by the stdlib ``zoneinfo`` tz database."""

    def resolve(self, name: str) -> DisplayZone | None:
        """The zone ``name`` designates, or ``None`` when the tz database has no such key.

        ``UTC`` short-circuits to the stdlib constant, so a deployment (or an image shipped
        without a tz database) resolves the default without a lookup, matching the composition
        root's own short-circuit. A malformed key surfaces as ``ValueError`` from ``ZoneInfo``,
        and an unknown one as ``ZoneInfoNotFoundError``; both become ``None`` rather than raising.
        """
        if name == UTC_ZONE_NAME:
            return UTC_DISPLAY
        try:
            return DisplayZone(name=name, tz=ZoneInfo(name))
        except (ZoneInfoNotFoundError, ValueError):
            return None


ZONEINFO_RESOLVER = ZoneInfoResolver()
"""The shared instance: the codec's decode default and the composition root's injected resolver."""
