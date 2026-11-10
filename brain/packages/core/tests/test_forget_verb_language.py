from datetime import UTC, datetime, timedelta

import pytest

from cortex_core import MemoryRecord
from cortex_core.forget_unnamed import unnamed

_AT = datetime(2026, 11, 10, 2, 0, 0, tzinfo=UTC)
_ROWS = (
    ("door", "User: Merke dir, mein Türcode ist 7319.\nAssistant: Notiert."),
    ("den", "User: Remember that the den alarm code is 7319.\nAssistant: Noted."),
    ("hat", "User: Remember that my hat locker is 7319.\nAssistant: Noted."),
    ("care", "User: Remember that the care home code is 7319.\nAssistant: Noted."),
    ("son", "User: Remember that my son's school code is 7319.\nAssistant: Noted."),
)


def _listed(query: str) -> list[str]:
    records = [
        MemoryRecord(id=name, text=text, embedding=(1.0, 0.0), at=_AT + timedelta(minutes=i))
        for i, (name, text) in enumerate(_ROWS)
    ]
    kept = {record.id for record in unnamed(records, "7319", query)}
    return sorted(name for name, _ in _ROWS if name not in kept)


@pytest.mark.parametrize(
    ("query", "listed"),
    [
        ("FORGET THE DEN ALARM CODE 7319, KEEP THE REST.", ["den"]),
        ("FORGET MY SON'S CODE 7319, KEEP THE REST.", ["son"]),
        ("Forget the den alarm code 7319, keep the rest.", ["den"]),
        ("REMOVE THE CARE HOME CODE 7319, KEEP THE REST.", ["care"]),
        ("Jürgen: forget den code 7319, keep the rest", ["den"]),
        ("FORGET THE DEN CODE 7319.", ["den"]),
    ],
)
def test_an_english_forget_verb_still_reads_a_word_of_another_list_as_a_fact(
    query: str, listed: list[str]
) -> None:
    assert _listed(query) == listed


@pytest.mark.parametrize(
    ("query", "listed"),
    [
        ("VERGISS DEN TÜRCODE 7319, ALLES ANDERE BLEIBT.", ["door"]),
        ("OUBLIE SON CODE 7319, GARDE LE RESTE.", []),
        ("LÖSCHE DEN TÜRCODE 7319, BEHALTE DEN REST.", ["door"]),
    ],
)
def test_a_forget_verb_of_another_language_reads_its_function_words_as_none(
    query: str, listed: list[str]
) -> None:
    assert _listed(query) == listed


def test_a_row_either_reading_keeps_is_kept() -> None:
    assert _listed("VERGISS DEN CODE 7319.") == ["den"]
