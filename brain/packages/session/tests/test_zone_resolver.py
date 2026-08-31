from zoneinfo import ZoneInfo

import pytest

from cortex_core import UTC_DISPLAY, DisplayZone
from cortex_session import ZONEINFO_RESOLVER, ZoneInfoResolver


def test_utc_short_circuits_to_the_stdlib_constant() -> None:
    assert ZoneInfoResolver().resolve("UTC") is UTC_DISPLAY


def test_a_known_key_resolves_to_that_zone() -> None:
    resolved = ZoneInfoResolver().resolve("America/New_York")
    assert resolved == DisplayZone(name="America/New_York", tz=ZoneInfo("America/New_York"))


@pytest.mark.parametrize("bad", ["Mars/Olympus", "not a zone", "../../etc/passwd", ""])
def test_an_unknown_or_malformed_key_answers_none(bad: str) -> None:
    assert ZoneInfoResolver().resolve(bad) is None


def test_the_shared_instance_is_a_resolver() -> None:
    assert isinstance(ZONEINFO_RESOLVER, ZoneInfoResolver)
