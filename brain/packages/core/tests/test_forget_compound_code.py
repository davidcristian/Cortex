from datetime import UTC, datetime, timedelta

import pytest

from cortex_core import MemoryRecord
from cortex_core.forget_unnamed import asks_to_keep, unnamed
from cortex_core.memory_values import code_stem

_AT = datetime(2026, 11, 9, 6, 0, 0, tzinfo=UTC)
_ROWS = (
    ("door", "User: Remember that my door code is 7319.\nAssistant: Noted."),
    ("shed", "User: Remember that the shed padlock code is also 7319.\nAssistant: Noted."),
    ("rad", "User: Merke dir, mein Fahrradschloss hat den Code 7319.\nAssistant: Notiert."),
)


def _kept(query: str) -> list[str]:
    rows = [
        MemoryRecord(id=name, text=text, embedding=(1.0, 0.0), at=_AT + timedelta(minutes=i))
        for i, (name, text) in enumerate(_ROWS)
    ]
    return sorted(record.id for record in unnamed(rows, "7319", query))


@pytest.mark.parametrize(
    "query",
    [
        "Forget 7319.",
        "Forget the code 7319.",
        "Forget my pincode 7319.",
        "Forget the doorbell 7319 code.",
    ],
)
def test_a_value_named_by_no_fact_word_asks_for_every_row(query: str) -> None:
    assert _kept(query) == []


def test_a_compound_code_word_naming_no_row_keeps_every_row() -> None:
    assert _kept("Forget my passcode 7319.") == ["door", "rad", "shed"]


@pytest.mark.parametrize(
    ("query", "kept"),
    [
        ("Forget the doorcode 7319, keep everything else.", ["rad", "shed"]),
        ("Forget my door code 7319, keep everything else.", ["rad", "shed"]),
        ("Vergiss den Fahrradcode 7319, alles andere bleibt.", ["door", "rad", "shed"]),
        ("Forget 7319 but keep the doorcode.", ["door", "rad", "shed"]),
    ],
)
def test_the_stem_of_a_compound_code_word_names_only_the_same_whole_word(
    query: str, kept: list[str]
) -> None:
    assert _kept(query) == kept


def test_a_keep_clause_naming_a_compound_keeps_no_row_the_compound_only_starts() -> None:
    assert asks_to_keep(_ROWS[0][1], "Forget 7319, keep the doorcode.")
    assert not asks_to_keep(_ROWS[2][1], "Forget 7319, keep the Fahrradcode.")


@pytest.mark.parametrize(
    ("word", "stem"),
    [
        ("doorcode", "door"),
        ("Fahrradcodes", "fahrrad"),
        ("Türnummer", "tür"),
        ("Postleitzahl", "postleit"),
        ("passcode", "pass"),
        ("pincode", None),
        ("code", None),
        ("Nummernschild", None),
        ("door", None),
    ],
)
def test_a_compound_code_word_gives_the_part_before_its_code_word(
    word: str, stem: str | None
) -> None:
    assert code_stem(word) == stem


def test_a_compound_naming_a_row_deleted_earlier_keeps_the_rows_it_does_not_name() -> None:
    door, *others = (
        MemoryRecord(id=name, text=text, embedding=(1.0, 0.0), at=_AT + timedelta(minutes=i))
        for i, (name, text) in enumerate(_ROWS)
    )
    query = "Forget the doorcode 7319, keep everything else."
    kept = unnamed(others, "7319", query, deleted=[door.text])
    assert sorted(record.id for record in kept) == ["rad", "shed"]


_COMPOUND_ROWS = (
    ("rad", "User: Merke dir, mein Fahrradcode ist 7319.\nAssistant: Notiert."),
    ("plz", "User: Merke dir, meine Postleitzahl ist 7319.\nAssistant: Notiert."),
    ("haus", "User: Merke dir, mein Haustürcode ist 7319.\nAssistant: Notiert."),
    ("pass", "User: Remember that my passcode is 7319.\nAssistant: Noted."),
    ("pin", "User: Remember that my pincode is 7319.\nAssistant: Noted."),
)


def _kept_of_compounds(query: str) -> list[str]:
    rows = [
        MemoryRecord(id=name, text=text, embedding=(1.0, 0.0), at=_AT + timedelta(minutes=i))
        for i, (name, text) in enumerate(_COMPOUND_ROWS)
    ]
    return sorted(record.id for record in unnamed(rows, "7319", query))


@pytest.mark.parametrize(
    ("query", "kept"),
    [
        ("Forget the Fahrradcode 7319 but keep the Postleitzahl.", ["haus", "pass", "pin", "plz"]),
        ("Vergiss 7319, behalte den Fahrradcode.", ["haus", "pass", "pin", "plz", "rad"]),
        ("Vergiss den Fahrradcode 7319, alles andere bleibt.", ["haus", "pass", "pin", "plz"]),
        ("Vergiss meine Postleitzahl 7319, alles andere bleibt.", ["haus", "pass", "pin", "rad"]),
        ("Forget my passcode 7319 but keep my passport.", ["haus", "pin", "plz", "rad"]),
        ("Forget my pincode 7319 but keep the pin.", ["haus", "pass", "plz", "rad"]),
    ],
)
def test_the_stem_of_a_compound_code_word_in_a_row_names_that_row(
    query: str, kept: list[str]
) -> None:
    assert _kept_of_compounds(query) == kept


def test_a_keep_clause_naming_the_compound_a_row_holds_asks_to_keep_that_row() -> None:
    query = "Vergiss meinen Türcode, aber behalte die Postleitzahl."
    assert asks_to_keep(_COMPOUND_ROWS[1][1], query)
    assert not asks_to_keep(_COMPOUND_ROWS[0][1], query)
