from datetime import UTC, datetime, timedelta

import pytest

from cortex_core import MemoryRecord
from cortex_core.forget_unnamed import asks_to_keep, unnamed

_AT = datetime(2026, 11, 9, 9, 0, 0, tzinfo=UTC)
_ROWS = (
    ("door", "User: Remember that my door code is 7319.\nAssistant: Noted."),
    ("passport", "User: Remember that my passport number ends in 7319.\nAssistant: Noted."),
    ("card", "User: Remember that my card PIN is 7319.\nAssistant: Noted."),
    ("bell", "User: Remember that the doorbell battery model is 7319.\nAssistant: Noted."),
    ("zip", "User: Remember that my zip code is 7319.\nAssistant: Noted."),
    ("plz", "User: Merke dir, meine Postleitzahl ist 7319.\nAssistant: Notiert."),
    ("bike", "User: Remember that my bike-lock code is 7319.\nAssistant: Noted."),
)
_MIXED = (
    ("tuer", "User: Merke dir, mein Türcode ist 7319.\nAssistant: Notiert."),
    ("den", "User: Remember that the den alarm code is 7319.\nAssistant: Noted."),
    ("hat", "User: Remember that my hat locker is 7319.\nAssistant: Noted."),
    ("rad", "User: Merke dir, mein Fahrradcode ist 7319.\nAssistant: Notiert."),
    ("haus", "User: Merke dir, mein Haustür Code ist 7319.\nAssistant: Notiert."),
)
_EVERY = sorted(name for name, _ in _ROWS)


def _listed(query: str, rows: tuple[tuple[str, str], ...] = _ROWS) -> list[str]:
    records = [
        MemoryRecord(id=name, text=text, embedding=(1.0, 0.0), at=_AT + timedelta(minutes=i))
        for i, (name, text) in enumerate(rows)
    ]
    kept = {record.id for record in unnamed(records, "7319", query)}
    return sorted(name for name, _ in rows if name not in kept)


@pytest.mark.parametrize(
    ("query", "listed"),
    [
        ("Forget my passcode 7319, keep everything else.", []),
        ("Forget the carcode 7319, keep everything else.", []),
        ("Forget the doorcode 7319, keep everything else.", ["door"]),
        ("Forget my zip code 7319, keep everything else.", ["zip"]),
        ("Forget my bike-lock code 7319, keep everything else.", ["bike"]),
        ("Forget my bikelock-code 7319, keep everything else.", []),
        ("Vergiss meine Postleitzahl 7319, alles andere bleibt.", ["plz"]),
    ],
)
def test_a_stem_names_only_the_same_whole_word_or_compound(query: str, listed: list[str]) -> None:
    assert _listed(query) == listed


@pytest.mark.parametrize(
    ("query", "listed"),
    [
        ("Vergiss den Fahrradcode 7319, alles andere bleibt.", ["rad"]),
        ("Vergiss den Türcode 7319, alles andere bleibt.", ["tuer"]),
        ("Vergiss den Türcode 7319.", ["tuer"]),
    ],
)
def test_a_german_compound_names_its_own_compound_and_not_a_word_it_ends(
    query: str, listed: list[str]
) -> None:
    assert _listed(query, _MIXED) == listed


@pytest.mark.parametrize(
    ("query", "listed"),
    [
        ("Forget my PIN 7319, keep everything else.", ["card"]),
        ("Forget my pin code 7319, keep everything else.", ["card"]),
        ("Forget 7319 but keep my pin code.", []),
        ("Forget 7319 but keep my zip code.", []),
        ("Forget 7319 but keep the Postleitzahl.", []),
        ("Forget 7319, keep the shed one.", []),
    ],
)
def test_a_keep_clause_lists_only_rows_a_whole_word_to_forget_names(
    query: str, listed: list[str]
) -> None:
    assert _listed(query) == listed


@pytest.mark.parametrize("query", ["Forget 7319.", "Forget the code 7319.", "Forget my PIN 7319."])
def test_a_message_with_no_keep_clause_and_no_fact_word_asks_for_every_row(query: str) -> None:
    assert _listed(query) == _EVERY


def test_a_code_word_names_rows_only_when_no_fact_word_does() -> None:
    phone = ("phone", "User: Remember that my phone PIN is 7319.\nAssistant: Noted.")
    assert _listed("Forget my card PIN 7319, keep everything else.", (*_ROWS, phone)) == ["card"]
    assert _listed("Forget my PIN 7319, keep everything else.", (*_ROWS, phone)) == [
        "card",
        "phone",
    ]


@pytest.mark.parametrize(
    ("row", "query"),
    [
        (_ROWS[2][1], "Forget my door code but keep my PIN."),
        (_ROWS[2][1], "FORGET MY DOOR CODE BUT KEEP MY PIN."),
        (
            "User: My Wi-Fi password is 7319.\nAssistant: Noted.",
            "Forget the door code, keep the password.",
        ),
        (_ROWS[5][1], "Forget my door code but keep the Postleitzahl."),
        (_MIXED[1][1], "Vergiss bitte den code 7319 vom hat, keep the den"),
    ],
)
def test_a_keep_clause_naming_a_code_word_or_a_function_word_a_row_holds_keeps_it(
    row: str, query: str
) -> None:
    assert asks_to_keep(row, query)


@pytest.mark.parametrize(
    ("row", "query"),
    [
        (_ROWS[0][1], "Forget my door code but keep my PIN."),
        (_ROWS[1][1], "Forget my passcode but keep the pass."),
        (_ROWS[3][1], "Forget 7319, keep the doorcode."),
        (_ROWS[4][1], "Forget the door code, keep the code."),
    ],
)
def test_a_keep_clause_names_no_row_by_a_word_it_only_starts_or_by_any_code(
    row: str, query: str
) -> None:
    assert not asks_to_keep(row, query)


def test_a_mixed_language_message_keeps_every_row_its_forget_part_names_no_word_of() -> None:
    assert _listed("Vergiss bitte den code 7319 vom hat, keep the den", _MIXED) == []
    assert _listed("Forget 7319 bitte, aber behalte den hat", _MIXED) == []
