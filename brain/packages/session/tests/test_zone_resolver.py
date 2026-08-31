"""ZoneInfoResolver: the zoneinfo-backed edge lookup (ADR-0025 per-rule addendum).

The core's ``ZoneResolver`` port is tz-database-free; this adapter is the one place a name meets
``zoneinfo``. It is exercised directly here and end to end through the codec and the schedule
tools elsewhere. ``None`` (never an exception) is the "no such zone" answer every caller relies on.
"""

from zoneinfo import ZoneInfo

import pytest

from cortex_core import UTC_DISPLAY, DisplayZone
from cortex_session import ZONEINFO_RESOLVER, ZoneInfoResolver


def test_utc_short_circuits_to_the_stdlib_constant() -> None:
    """The default deployment resolves without consulting a tz database (an image shipped without
    one still boots), and it returns the same object the core carries."""
    assert ZoneInfoResolver().resolve("UTC") is UTC_DISPLAY


def test_a_known_key_resolves_to_that_zone() -> None:
    resolved = ZoneInfoResolver().resolve("America/New_York")
    assert resolved == DisplayZone(name="America/New_York", tz=ZoneInfo("America/New_York"))


@pytest.mark.parametrize("bad", ["Mars/Olympus", "not a zone", "../../etc/passwd", ""])
def test_an_unknown_or_malformed_key_answers_none(bad: str) -> None:
    """An unknown or malformed key returns ``None`` rather than raising, so every caller turns it
    into a correction or a corrupt-record failure rather than crashing. Covers both the not-found
    and the invalid-key paths ``zoneinfo`` distinguishes."""
    assert ZoneInfoResolver().resolve(bad) is None


def test_the_shared_instance_is_a_resolver() -> None:
    assert isinstance(ZONEINFO_RESOLVER, ZoneInfoResolver)
