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
from cortex_core.forget_clauses import after_but
from cortex_core.forget_unnamed import KEPT_LINE
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 15, 6, 0, 0, tzinfo=UTC)
_ROWS = {
    "locker": "User: Remember that my locker code is 4242.\nAssistant: Noted.",
    "phone": "User: Remember that my phone is 0721 555 4242.\nAssistant: Noted.",
    "card": "User: Remember that my card is 4111 1111 1111 4242.\nAssistant: Noted.",
    "casier": "User: Retiens que le code du casier est 4242.\nAssistant: Noté.",
    "carte": "User: Retiens que ma carte est 4111 1111 1111 4242.\nAssistant: Noté.",
    "telephone": "User: Retiens que mon téléphone est 0721 555 4242.\nAssistant: Noté.",
    "spind": "User: Merke dir, der Code vom Spind ist 4242.\nAssistant: Notiert.",
    "karte": "User: Merke dir, meine Karte ist 4111 1111 1111 4242.\nAssistant: Notiert.",
    "handy": "User: Merke dir, mein Handy ist 0721 555 4242.\nAssistant: Notiert.",
    "gimnasio": "User: Recuerda que el código del gimnasio es 4242.\nAssistant: Anotado.",
    "tarjeta": "User: Recuerda que mi tarjeta es 4111 1111 1111 4242.\nAssistant: Anotado.",
    "telefono": "User: Recuerda que mi teléfono es 0721 555 4242.\nAssistant: Anotado.",
    "dulap": "User: Ține minte că codul de la dulap este 4242.\nAssistant: Notat.",
    "cardul": "User: Ține minte că cardul meu este 4111 1111 1111 4242.\nAssistant: Notat.",
    "telefonul": "User: Ține minte că telefonul meu este 0721 555 4242.\nAssistant: Notat.",
}
_ENGLISH = ("locker", "card", "phone")
_FRENCH = ("casier", "carte", "telephone")
_GERMAN = ("spind", "karte", "handy")
_SPANISH = ("gimnasio", "tarjeta", "telefono")
_ROMANIAN = ("dulap", "cardul", "telefonul")


async def _forget(query: str, *ids: str) -> tuple[str | None, list[str]]:
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
    card = await tool.card(call)
    await tool.invoke(call)
    return card, sorted(hit.record.id for hit in await store.search((1.0, 0.0), k=10))


async def test_a_but_after_a_word_for_all_and_a_value_keeps_the_row_it_names() -> None:
    card, left = await _forget("Forget all 4242 but the card.", *_ENGLISH)
    assert left == ["card"]
    assert card is not None
    listed, kept = card.split(KEPT_LINE)
    assert "locker code is 4242" in listed
    assert "0721 555 4242" in listed
    assert "4111 1111 1111 4242" in kept
    assert "4111 1111 1111 4242" not in listed


@pytest.mark.parametrize(
    ("query", "ids", "left"),
    [
        ("Forget every 4242 but my card.", _ENGLISH, ["card"]),
        ("Forget all 4242, but the card.", _ENGLISH, ["card"]),
        ("Forget all 4242 but the card I need.", _ENGLISH, ["card"]),
        ("Forget all 4242 yet the card stays.", _ENGLISH, ["card"]),
        ("Forget all 4242 but leave the card and the phone.", _ENGLISH, ["card", "phone"]),
        ("Forget 4242 but the card.", _ENGLISH, ["card", "locker", "phone"]),
        ("Forget the card 4242 and the phone, but the card I need.", _ENGLISH, ["card", "locker"]),
        ("Forget all 4242 but la carte.", ("locker", "carte", "phone"), ["carte"]),
        ("Oublie tous les 4242 mais la carte.", _FRENCH, ["carte"]),
        ("Vergiss alle 4242 aber die Karte.", _GERMAN, ["karte"]),
        ("Vergiss alle 4242, aber die Karte brauche ich.", _GERMAN, ["karte"]),
        ("Olvida todas las 4242 pero la tarjeta.", _SPANISH, ["tarjeta"]),
        ("Șterge toate 4242 dar cardul.", _ROMANIAN, ["cardul", "dulap", "telefonul"]),
    ],
)
async def test_a_word_for_but_after_the_forget_verb_keeps_each_row_its_clause_names(
    query: str, ids: tuple[str, ...], left: list[str]
) -> None:
    assert (await _forget(query, *ids))[1] == left


@pytest.mark.parametrize(
    ("query", "ids", "left"),
    [
        ("Forget every 4242, but not the card.", _ENGLISH, ["card"]),
        ("Forget all but the card.", _ENGLISH, ["card", "locker", "phone"]),
        ("Forget every 4242 but keep the card.", _ENGLISH, ["card", "phone"]),
        ("Forget my phone 4242 but keep Anna's phone.", _ENGLISH, ["card", "locker"]),
    ],
)
async def test_a_but_before_a_keep_clause_keeps_what_the_keep_clause_keeps(
    query: str, ids: tuple[str, ...], left: list[str]
) -> None:
    assert (await _forget(query, *ids))[1] == left


@pytest.mark.parametrize(
    ("query", "ids", "left"),
    [
        ("Forget the card 4242, but do it quietly.", _ENGLISH, ["locker", "phone"]),
        ("Forget the card 4242 but do it quietly.", _ENGLISH, ["locker", "phone"]),
        ("Forget all 4242 but quickly.", _ENGLISH, []),
        ("Forget every 4242 but do it now.", _ENGLISH, []),
        ("Forget every 4242 but.", _ENGLISH, []),
        ("But forget the card 4242.", _ENGLISH, ["locker", "phone"]),
        ("Vergiss alle 4242, aber schnell.", _GERMAN, []),
        ("Oublie tous les 4242, mais vite.", _FRENCH, []),
        ("Olvida todas las 4242, pero rápido.", _SPANISH, []),
    ],
)
async def test_a_word_for_but_naming_no_row_keeps_no_row(
    query: str, ids: tuple[str, ...], left: list[str]
) -> None:
    assert (await _forget(query, *ids))[1] == left


@pytest.mark.parametrize(
    "query",
    [
        "Forget the locker 4242 but the card too.",
        "Forget the locker 4242 but also the card.",
        "Forget the locker 4242 but the card as well.",
        "Forget the locker 4242, but forget the card too.",
        "Forget the locker 4242 but delete the card.",
    ],
)
async def test_a_but_clause_adding_a_row_or_holding_a_forget_verb_keeps_no_row(query: str) -> None:
    assert (await _forget(query, *_ENGLISH))[1] == ["phone"]


@pytest.mark.parametrize(
    ("query", "words"),
    [
        ("Forget all 4242 but the card.", ["the", "card"]),
        ("Forget all 4242, but the card. And the phone.", ["the", "card"]),
        (
            "Forget all 4242 yet the card, but my phone I need.",
            ["the", "card", "my", "phone", "i", "need"],
        ),
        ("Forget all 4242 but the card but the phone.", ["the", "card", "but", "the", "phone"]),
        ("But the card, forget 4242.", []),
        ("But forget all 4242 but the card.", ["the", "card"]),
        ("Forget every 4242, but not the card.", []),
        ("Forget my phone but keep Anna's phone.", []),
        ("Keep the card but drop the phone.", []),
        ("Forget all 4242 but.", []),
        ("Forget all 4242 but the card too.", []),
        ("Forget all 4242 but the card as well.", []),
        ("Forget all 4242 but erase the card.", []),
        ("Forget all 4242 but the card, also the phone.", ["the", "card"]),
    ],
)
def test_the_reader_returns_the_words_after_a_word_for_but_that_follows_a_forget_verb(
    query: str, words: list[str]
) -> None:
    assert after_but(query) == words
