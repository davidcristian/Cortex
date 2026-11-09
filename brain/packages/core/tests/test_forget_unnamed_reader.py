from datetime import UTC, datetime, timedelta

import pytest

from cortex_core import MemoryRecord
from cortex_core.forget_unnamed import unnamed

_AT = datetime(2026, 11, 9, 4, 0, 0, tzinfo=UTC)
_BIKE = "User: Remember that my bike lock code is 7319.\nAssistant: Noted."
_SHED = "User: Remember that the shed padlock code is also 7319.\nAssistant: Noted."
_USER = "User: Remember that my user id is 7319.\nAssistant: Noted."


def _record(
    record_id: str, text: str, session_id: str | None = None, minutes: int = 0
) -> MemoryRecord:
    return MemoryRecord(
        id=record_id,
        text=text,
        embedding=(1.0, 0.0),
        at=_AT + timedelta(minutes=minutes),
        scope="global",
        session_id=session_id,
    )


def _kept(query: str, *rows: MemoryRecord, session_id: str | None = None) -> list[str]:
    return [record.id for record in unnamed(rows, "7319", query, (), session_id)]


_TWO = (_record("bike", _BIKE), _record("shed", _SHED, minutes=1))


@pytest.mark.parametrize(
    "query",
    [
        "Forget my bike lock code 7319.",
        "Forget my bike lock code 7319, keep everything else.",
        "Forget my bike lock code 7319, that's all.",
        "Forget all about my bike lock code 7319.",
        "Forget everything about my bike lock code 7319.",
        "Forget all my bike lock codes, it is 7319.",
        "Forget my bike lock code 7319 and nothing else, keep all the others.",
        "Forget my bike lock code 7319. That is all.",
        "Oublie le code de mon bike lock 7319, c'est tout.",
        "Forget my bike lock code 7319, mein Hund ist tot.",
        "Vergiss den bike lock Code 7319, alle anderen behalten.",
        "Forget everything about it, my bike lock code 7319.",
        "Forget my bike lock code 7319 but keep all other 7319s.",
        "Forget the bike lock code 7319, not everything else 7319 opens.",
        "Forget it all, my bike lock code 7319.",
        "Forget all about 7319, my bike lock code.",
    ],
)
def test_a_word_for_all_outside_the_forget_keeps_the_fact_the_message_does_not_name(
    query: str,
) -> None:
    assert _kept(query, *_TWO) == ["shed"]


@pytest.mark.parametrize(
    "query",
    [
        "Forget my bike lock code 7319 everywhere.",
        "Forget all of 7319.",
        "Forget my bike lock code, it is 7319, and every other 7319 too.",
        "Forget my bike lock code 7319, everywhere.",
        "Oublie le code de mon bike lock, c'est 7319, partout.",
        "Vergiss den bike lock Code 7319 überall.",
        "Forget my bike lock code and all 7319s.",
        "Forget my bike lock code 73 19 everywhere.",
    ],
)
def test_a_word_for_all_beside_the_value_asks_for_every_row(query: str) -> None:
    assert _kept(query, *_TWO) == []


@pytest.mark.parametrize(
    "query",
    [
        "Forget it all, it is 7319.",
        "Forget everything, 7319.",
        "Delete them all, the 7319 ones.",
        "Oublie tout, c'est 7319.",
    ],
)
def test_a_word_for_all_in_a_message_naming_no_fact_asks_for_every_row(query: str) -> None:
    rows = (*_TWO, _record("own", _BIKE, "chat-a", 2))
    assert _kept(query, *rows, session_id="chat-a") == []


@pytest.mark.parametrize(
    "query", ["Forget it all.", "Forget everything.", "Delete them all.", "Oublie tout."]
)
def test_a_word_for_all_with_no_value_reads_as_a_forget_naming_no_word(query: str) -> None:
    assert _kept(query, *_JUST_ROWS, session_id="chat-a") == ["old", "other"]


def test_a_word_for_all_after_the_verb_before_a_label_reads_the_label() -> None:
    assert _kept("Forget all my bike lock codes.", *_TWO) == ["shed"]


@pytest.mark.parametrize(
    ("query", "kept"),
    [
        ("Forget my user id 7319.", ["shed"]),
        ("Forget the user id, it is 7319.", ["shed"]),
        ("Forget my shed padlock code 7319.", ["user"]),
        ("Forget 7319.", []),
        ("Forget the one that is 7319.", []),
    ],
)
def test_a_word_of_a_row_prefix_can_name_a_fact(query: str, kept: list[str]) -> None:
    rows = (_record("user", _USER), _record("shed", _SHED, minutes=1))
    assert _kept(query, *rows) == kept


def test_the_assistant_prefix_names_no_row_and_the_word_can_name_one() -> None:
    assistant = "User: My assistant's desk code is 7319.\nAssistant: Noted."
    rows = (_record("desk", assistant), _record("shed", _SHED, minutes=1))
    assert _kept("Forget my assistant's desk code 7319.", *rows) == ["shed"]
    assert _kept("Forget the desk one, 7319.", *rows) == ["shed"]


_JUST_ROWS = (
    _record("old", _BIKE, "chat-a", 0),
    _record("new", _BIKE, "chat-a", 1),
    _record("other", _SHED, "chat-b", 2),
)


@pytest.mark.parametrize(
    "query",
    ["Actually forget it", "Forget that.", "Forget it, please.", "Forget that number."],
)
def test_a_forget_naming_no_word_lists_only_the_newest_row_the_chat_stored(query: str) -> None:
    assert _kept(query, *_JUST_ROWS, session_id="chat-a") == ["old", "other"]


@pytest.mark.parametrize("query", ["Actually forget it", "Forget that.", "Forget it, please."])
def test_a_forget_naming_no_word_keeps_every_row_when_the_chat_stored_none(query: str) -> None:
    assert _kept(query, *_TWO, session_id="chat-a") == ["bike", "shed"]


@pytest.mark.parametrize(
    "query", ["Forget 7319.", "Forget it, it is 7319.", "Forget that one, 7319."]
)
def test_a_forget_naming_the_value_and_no_word_still_asks_for_every_row(query: str) -> None:
    assert _kept(query, *_JUST_ROWS, session_id="chat-a") == []


def test_a_call_with_no_message_keeps_no_row() -> None:
    assert _kept(" ", *_JUST_ROWS, session_id="chat-a") == []
