from datetime import UTC, datetime, timedelta

import pytest

from cortex_core.memory_age import aged, written_ago

_NOW = datetime(2026, 10, 26, 2, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("elapsed", "words"),
    [
        (timedelta(days=21, hours=5), "21 days ago"),
        (timedelta(days=1, hours=23), "1 day ago"),
        (timedelta(hours=2, minutes=59), "2 hours ago"),
        (timedelta(hours=1), "1 hour ago"),
        (timedelta(minutes=5), "5 minutes ago"),
        (timedelta(minutes=1), "1 minute ago"),
        (timedelta(seconds=59), "just now"),
        (timedelta(0), "just now"),
        (timedelta(microseconds=-1), "age unknown"),
        (timedelta(hours=-3), "age unknown"),
    ],
)
def test_an_age_is_named_in_its_largest_whole_unit(elapsed: timedelta, words: str) -> None:
    assert written_ago(_NOW - elapsed, _NOW) == words


def test_a_memory_dated_after_now_does_not_read_newer_than_a_later_one() -> None:
    ahead = aged("The gym is on Elm Street.", _NOW + timedelta(hours=2), _NOW)
    later = aged("The gym moved to Oak Lane.", _NOW - timedelta(minutes=5), _NOW)
    assert ahead == "(age unknown) The gym is on Elm Street."
    assert later == "(5 minutes ago) The gym moved to Oak Lane."


def test_an_aged_text_starts_with_its_age_in_brackets() -> None:
    assert aged("I like tea", _NOW - timedelta(days=9), _NOW) == "(9 days ago) I like tea"
