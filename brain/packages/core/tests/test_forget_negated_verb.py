from datetime import UTC, datetime, timedelta

import pytest

from cortex_core import (
    FORGET_CHOSEN_TOOL_NAME,
    GLOBAL_MEMORY_SCOPE,
    ForgetChosenTool,
    InMemoryMemoryStore,
    MemoryRecord,
    ToolCall,
)
from cortex_core.forget_clauses import parts
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 24, 6, 0, 0, tzinfo=UTC)
_ROWS = {
    "locker": "User: Remember that my locker code is 4242.\nAssistant: Noted.",
    "card": "User: Remember that my card is 4111 1111 1111 4242.\nAssistant: Noted.",
    "phone": "User: Remember that my phone is 0721 555 4242.\nAssistant: Noted.",
    "casier": "User: Retiens que le code du casier est 4242.\nAssistant: Noté.",
    "carte": "User: Retiens que ma carte est 4111 1111 1111 4242.\nAssistant: Noté.",
    "telephone": "User: Retiens que mon téléphone est 0721 555 4242.\nAssistant: Noté.",
    "spind": "User: Merke dir, der Code vom Spind ist 4242.\nAssistant: Notiert.",
    "karte": "User: Merke dir, meine Karte ist 4111 1111 1111 4242.\nAssistant: Notiert.",
    "handy": "User: Merke dir, mein Handy ist 0721 555 4242.\nAssistant: Notiert.",
    "don": "User: Remember that Don's phone is 0744 555 4242.\nAssistant: Noted.",
}
_ENGLISH = ("card", "phone", "locker")
_FRENCH = ("carte", "telephone", "casier")
_GERMAN = ("karte", "handy", "spind")


async def _left(query: str, ids: tuple[str, ...]) -> list[str]:
    store = InMemoryMemoryStore()
    for i, name in enumerate(ids):
        at = _AT + timedelta(minutes=i)
        record = MemoryRecord(
            id=name, text=_ROWS[name], embedding=(1.0, 0.0), at=at, session_id="chat-a"
        )
        await store.add(record)
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(session_id="chat-new", turn_id="t1", query=query)
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": "4242"}, stamp=stamp)
    await tool.card(call)
    await tool.invoke(call)
    return sorted(hit.record.id for hit in await store.search((1.0, 0.0), k=10))


@pytest.mark.parametrize(
    ("query", "ids"),
    [
        ("Oublie 4242, n'efface pas la carte.", _FRENCH),
        ("Oublie 4242. N'oublie pas la carte.", _FRENCH),
        ("Oublie 4242, mais n'oublie pas la carte.", _FRENCH),
        ("Je ne veux pas oublier la carte, oublie 4242.", _FRENCH),
        ("Vergiss 4242, lösch nicht die Karte.", _GERMAN),
        ("Vergiss 4242, vergiss die Karte nicht.", _GERMAN),
        ("Vergiss 4242. Lösche die Karte nicht.", _GERMAN),
        ("Vergiss 4242 und die Karte nicht.", _GERMAN),
        ("Vergiss 4242, die Karte nicht löschen.", _GERMAN),
        ("Forget all 4242 though not the card.", _ENGLISH),
    ],
)
async def test_a_negation_inside_a_clause_with_a_forget_verb_keeps_the_row_it_names(
    query: str, ids: tuple[str, ...]
) -> None:
    assert ids[0] in await _left(query, ids)


@pytest.mark.parametrize(
    ("query", "ids", "gone"),
    [
        ("Oublie 4242, n'efface pas la carte.", _FRENCH, "casier"),
        ("Vergiss 4242, vergiss die Karte nicht.", _GERMAN, "spind"),
        ("Forget 4242 not the card.", _ENGLISH, "locker"),
    ],
)
async def test_a_negated_forget_verb_still_deletes_the_rows_the_first_clause_asks_for(
    query: str, ids: tuple[str, ...], gone: str
) -> None:
    left = await _left(query, ids)
    assert ids[0] in left
    assert gone not in left


@pytest.mark.parametrize(
    "query",
    [
        "Vergiss alle 4242, nicht die Karte.",
        "Vergiss alle 4242, lösch nicht die Karte.",
        "Vergiss alle 4242, lösch die Karte nicht.",
        "Vergiss alle 4242, die Karte nicht löschen.",
        "Vergiss alle 4242, aber lösch nicht die Karte.",
        "Vergiss alle 4242, lösch nicht die Karte und das Handy.",
        "Lösch nicht die Karte, vergiss alle 4242.",
    ],
)
async def test_a_forget_of_every_value_reads_a_negated_forget_verb_as_a_keep_clause_opening(
    query: str,
) -> None:
    assert await _left(query, _GERMAN) == ["handy", "karte"]


@pytest.mark.parametrize(
    ("query", "ids"),
    [
        ("Vergiss alle 4242, lösch nicht.", _GERMAN),
        ("Oublie tous les 4242, n'efface pas le casier.", _FRENCH),
        ("Oublie tous les 4242, pas le casier.", _FRENCH),
        ("Forget all 4242, not the locker.", _ENGLISH),
        ("Forget all 4242, don't delete the locker.", _ENGLISH),
        ("Vergiss alle 4242, nicht den Spind.", _GERMAN),
    ],
)
async def test_a_forget_of_every_value_beside_a_keep_clause_naming_no_card_or_phone_keeps_all(
    query: str, ids: tuple[str, ...]
) -> None:
    assert await _left(query, ids) == sorted(ids)


@pytest.mark.parametrize(
    ("query", "left"),
    [
        ("Forget all 4242, don't delete the card.", ["card"]),
        ("Forget all 4242, don't delete the phone.", ["phone"]),
        ("Forget all 4242. Don't remove the card.", ["card"]),
        ("Forget all 4242 but don't erase the card.", ["card"]),
        ("Don't forget the card, forget all 4242.", ["card"]),
        ("Forget all 4242, not the card.", ["card"]),
        ("Forget all 4242, do not forget the card.", ["card"]),
        ("Forget all 4242, the card isn't needed.", ["locker", "phone"]),
        ("Forget all 4242, I don't need the card.", ["card", "locker", "phone"]),
        ("Forget all 4242, won't delete the card.", ["card"]),
    ],
)
async def test_a_forget_of_every_value_reads_the_word_before_a_contracted_negation_in_its_clause(
    query: str, left: list[str]
) -> None:
    assert await _left(query, _ENGLISH) == left


@pytest.mark.parametrize(
    ("query", "left"),
    [
        ("Forget Don, don't remove the card.", ["card", "phone"]),
        ("Forget Don don't remove the card.", ["card", "phone"]),
        ("Forget the card, don't forget Don.", ["don", "phone"]),
        ("Forget the card but don't forget Don.", ["don", "phone"]),
        ("Don't forget Don, forget the card.", ["don", "phone"]),
    ],
)
async def test_a_forget_naming_a_row_by_the_word_before_a_contracted_negation_reads_that_row(
    query: str, left: list[str]
) -> None:
    assert await _left(query, ("card", "phone", "don")) == left


@pytest.mark.parametrize(
    "query",
    ["Forget 4242 on the card I no longer use.", "Forget 4242 on the card I do not use."],
)
async def test_a_negation_after_the_row_in_a_later_remark_still_deletes_the_row(
    query: str,
) -> None:
    assert "card" not in await _left(query, _ENGLISH)


@pytest.mark.parametrize(
    ("query", "forget", "keep"),
    [
        ("Oublie 4242, n'efface pas la carte.", "oublie 4242 n", "efface pas la carte"),
        ("Vergiss 4242, lösch nicht die Karte.", "vergiss 4242", "lösch nicht die karte"),
        ("Vergiss 4242, vergiss die Karte nicht.", "vergiss 4242", "vergiss die karte nicht"),
        ("Vergiss 4242 und die Karte nicht.", "vergiss 4242", "und die karte nicht"),
        ("Vergiss 4242, die Karte nicht löschen.", "vergiss 4242", "die karte nicht löschen"),
        ("Forget all 4242 though not the card.", "forget all 4242 though", "not the card"),
        ("Forget all 4242, don't delete the card.", "forget all 4242", "don t delete the card"),
        ("Forget all 4242, the card isn't needed.", "forget all 4242 the card", "isn t needed"),
        ("Vergiss nicht, die Karte zu löschen.", "die karte zu löschen", "vergiss nicht"),
        (
            "Lösche 4242 von der Karte die ich nicht mehr brauche.",
            "lösche 4242 von der karte die ich",
            "nicht mehr brauche",
        ),
        ("Forget the not so new shed padlock code.", "forget the not so new shed padlock code", ""),
    ],
)
def test_parts_reads_a_negation_inside_a_clause_with_a_forget_verb(
    query: str, forget: str, keep: str
) -> None:
    assert tuple(" ".join(tokens) for tokens in parts(query)) == (forget, keep)
