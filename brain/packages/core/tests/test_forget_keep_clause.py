from datetime import UTC, datetime, timedelta

import pytest

from cortex_core import MemoryRecord
from cortex_core.forget_unnamed import unnamed

_AT = datetime(2026, 11, 9, 5, 0, 0, tzinfo=UTC)
_BIKE = "User: Remember that my bike lock code is 7319.\nAssistant: Noted."
_SHED = "User: Remember that the shed padlock code is also 7319.\nAssistant: Noted."
_SHED_RECALL = "User: What is the shed padlock code?\nAssistant: It is 7319."


def _record(record_id: str, text: str, minutes: int = 0) -> MemoryRecord:
    return MemoryRecord(
        id=record_id,
        text=text,
        embedding=(1.0, 0.0),
        at=_AT + timedelta(minutes=minutes),
        scope="global",
        session_id=None,
    )


_TWO = (_record("bike", _BIKE), _record("shed", _SHED, 1))


def _kept(query: str, *rows: MemoryRecord) -> list[str]:
    return [record.id for record in unnamed(rows or _TWO, "7319", query)]


@pytest.mark.parametrize(
    "query",
    [
        "Forget my bike lock code 7319, keep the shed padlock one.",
        "Forget my bike lock code 7319 but not the shed one.",
        "Forget my bike lock code, not the shed one.",
        "Forget my bike lock code 7319 and not the shed one.",
        "Forget 7319, keep the shed one.",
        "Forget 7319 everywhere, but keep the shed one.",
        "Keep the shed padlock code and forget the bike lock code 7319.",
        "Can you keep the shed one and forget my bike lock code 7319?",
        "Forget my bike lock code 7319, but don't forget the shed one.",
        "Forget my bike lock code 7319, it is not the shed one.",
        "Forget my bike lock code 7319, it's not the shed one.",
        "Oublie le code du bike lock 7319, mais pas celui du shed.",
        "Oublie 7319, garde celui du shed.",
        "Vergiss den bike lock Code 7319, aber nicht den shed Code.",
        "Vergiss 7319, behalte den shed Code.",
        "Olvida el código del bike lock 7319, pero no el del shed.",
        "Uită codul de la bike lock 7319, dar nu pe cel de la shed.",
        "Uită 7319, păstrează codul de la shed.",
    ],
)
def test_a_fact_named_only_in_a_clause_asking_to_keep_is_kept(query: str) -> None:
    assert _kept(query) == ["shed"]


@pytest.mark.parametrize(
    ("query", "kept"),
    [
        ("Forget my bike lock code 7319, keep everything else.", ["shed"]),
        ("Forget the not so new shed padlock code 7319.", ["bike"]),
        ("Don't keep my bike lock code 7319.", ["shed"]),
        ("Do not keep the shed padlock code 7319.", ["bike"]),
        ("Forget my bike lock code 7319, don't keep the shed one either.", []),
        ("Ne garde pas le code du shed 7319.", ["bike"]),
        ("I keep forgetting it, forget my bike lock code 7319.", ["shed"]),
        ("Forget 7319.", []),
    ],
)
def test_a_negation_or_keep_verb_that_asks_for_no_keep_leaves_the_words_to_forget(
    query: str, kept: list[str]
) -> None:
    assert _kept(query) == kept


def test_a_word_also_named_outside_the_keep_clause_names_a_fact_to_forget() -> None:
    lock = _record("shed", "User: Remember that the shed lock code is 7319.\nAssistant: Noted.", 1)
    assert _kept("Forget my bike lock code 7319, keep the shed lock code.", _TWO[0], lock) == [
        "shed"
    ]
    assert _kept("Keep the bike one, forget the bike lock code 7319.") == ["shed"]


def test_a_row_named_by_a_keep_clause_and_by_a_word_to_forget_is_kept() -> None:
    lock = _record("shed", "User: Remember that the shed lock code is 7319.\nAssistant: Noted.", 1)
    assert _kept("Forget my lock codes 7319, keep the shed one.", _TWO[0], lock) == ["shed"]
    both = _record("both", "User: The bike shed code is 7319.\nAssistant: Noted.", 2)
    assert _kept("Forget the bike code 7319, keep the shed one.", _TWO[0], both) == ["both"]


def test_a_keep_clause_keeps_a_row_holding_the_value_only_in_its_reply() -> None:
    recall = _record("recall", _SHED_RECALL, 2)
    assert _kept("Forget 7319, keep the shed one.", _TWO[0], recall) == ["recall"]
    assert _kept("Forget 7319.", _TWO[0], recall) == []


def test_a_keep_verb_alone_names_no_fact() -> None:
    keeper = _record("keeper", "User: Keep the gate code 7319 handy.\nAssistant: Noted.", 2)
    assert _kept("Forget my bike lock code 7319, keep it.", _TWO[0], keeper) == ["keeper"]
    assert _kept("Forget 7319, keep it.", _TWO[0], keeper) == []
