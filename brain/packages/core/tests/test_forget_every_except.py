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
from cortex_core.forget_unnamed import KEPT_LINE, unnamed
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 15, 6, 0, 0, tzinfo=UTC)
_ROWS = {
    "locker": "User: Remember that my locker code is 4242.\nAssistant: Noted.",
    "gym": "User: Remember that my gym code is 4242.\nAssistant: Noted.",
    "phone": "User: Remember that my phone is 0721 555 4242.\nAssistant: Noted.",
    "card": "User: Remember that my card is 4111 1111 1111 4242.\nAssistant: Noted.",
    "badge": "User: Remember that my badge is 9000 4242.\nAssistant: Noted.",
    "casier": "User: Retiens que le code du casier est 4242.\nAssistant: Noté.",
    "carte": "User: Retiens que ma carte est 4111 1111 1111 4242.\nAssistant: Noté.",
    "telephone": "User: Retiens que mon téléphone est 0721 555 4242.\nAssistant: Noté.",
    "spind": "User: Merke dir, der Code vom Spind ist 4242.\nAssistant: Notiert.",
    "karte": "User: Merke dir, meine Karte ist 4111 1111 1111 4242.\nAssistant: Notiert.",
    "handy": "User: Merke dir, mein Handy ist 0721 555 4242.\nAssistant: Notiert.",
    "telefon": "User: Merke dir, mein Telefon ist 0721 555 4242.\nAssistant: Notiert.",
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


async def test_every_value_except_one_kind_lists_a_last_group_of_another_kind() -> None:
    card, left = await _forget("Forget every 4242 except the card.", "locker", "carte", "phone")
    assert left == ["carte"]
    assert card is not None
    listed, kept = card.split(KEPT_LINE)
    assert "locker code is 4242" in listed
    assert "0721 555 4242" in listed
    assert "4111 1111 1111 4242" in kept
    assert "0721 555 4242" not in kept


@pytest.mark.parametrize(
    ("query", "ids", "left"),
    [
        ("Forget every 4242 except the card.", _ENGLISH, ["card"]),
        ("Forget all 4242 except my card.", _ENGLISH, ["card"]),
        ("Forget every 4242, keep the card.", _ENGLISH, ["card"]),
        ("Forget every 4242. Keep the card.", _ENGLISH, ["card"]),
        ("Forget every 4242, not the card.", _ENGLISH, ["card"]),
        ("Forget every 4242 except the phone.", _ENGLISH, ["phone"]),
        ("Forget every 4242 except the card.", ("locker", "cardul", "telefonul"), ["cardul"]),
        ("Oublie tous les 4242 sauf la carte.", _FRENCH, ["carte"]),
        ("Oublie tous les 4242, garde la carte.", _FRENCH, ["carte"]),
        ("Vergiss alle 4242, behalte die Karte.", ("spind", "karte", "telefon"), ["karte"]),
        ("Olvida todas las 4242 excepto la tarjeta.", _SPANISH, ["tarjeta"]),
    ],
)
async def test_a_word_for_all_beside_a_keep_clause_lists_each_row_it_does_not_name(
    query: str, ids: tuple[str, ...], left: list[str]
) -> None:
    assert (await _forget(query, *ids))[1] == left


@pytest.mark.parametrize(
    ("query", "ids", "left"),
    [
        ("Forget 4242, except the card.", ("locker", "carte", "phone"), ["carte", "phone"]),
        ("Forget 4242, keep the card.", _ENGLISH, ["card", "phone"]),
        (
            "Forget every 4242 except the card and the phone.",
            (*_ENGLISH, "gym", "badge"),
            ["badge", "card", "phone"],
        ),
        ("Forget every 4242 except the card.", (*_ENGLISH, "badge"), ["badge", "card"]),
        ("Forget every 4242 except the phone.", (*_ENGLISH, "handy"), ["handy", "phone"]),
        (
            "Vergiss alle 4242, behalte die Karte, mein Handy auch.",
            (*_GERMAN, "phone"),
            ["handy", "karte", "phone"],
        ),
        ("Forget every 4242 except the locker.", _ENGLISH, ["card", "locker", "phone"]),
        ("Vergiss alle 4242, behalte die Karte.", _GERMAN, ["handy", "karte"]),
        ("Forget 4242 except every card.", _ENGLISH, ["card", "phone"]),
        ("Forget every 4242 except all the cards.", _ENGLISH, ["card", "phone"]),
        ("Forget every 4242 except the passport.", _ENGLISH, ["card", "locker", "phone"]),
        (
            "Forget every 4242 except the card and the passport.",
            _ENGLISH,
            ["card", "locker", "phone"],
        ),
        (
            "Forget every code 4242 except the card.",
            (*_ENGLISH, "badge"),
            ["badge", "card", "phone"],
        ),
        ("Forget everything about 4242 except the card.", _ENGLISH, ["card", "phone"]),
        ("Oublie 4242, sauf la carte.", _FRENCH, ["carte", "telephone"]),
        ("Vergiss 4242, behalte die Karte.", _GERMAN, ["handy", "karte"]),
        ("Olvida 4242, excepto la tarjeta.", _SPANISH, ["tarjeta", "telefono"]),
        ("Șterge toate 4242 exceptând cardul.", _ROMANIAN, ["cardul", "dulap", "telefonul"]),
    ],
)
async def test_a_keep_clause_with_no_word_for_all_beside_the_value_lists_only_the_whole_value(
    query: str, ids: tuple[str, ...], left: list[str]
) -> None:
    assert (await _forget(query, *ids))[1] == left


async def test_a_word_for_all_with_no_keep_clause_lists_every_row() -> None:
    assert (await _forget("Forget every 4242.", *_ENGLISH))[1] == []


@pytest.mark.parametrize(
    ("query", "ids", "left"),
    [
        (
            "Forget every 4242 except the card, my phone too.",
            (*_ENGLISH, "badge"),
            ["badge", "card", "phone"],
        ),
        (
            "Forget every 4242 except the card, the phone and the badge too.",
            (*_ENGLISH, "badge", "gym"),
            ["badge", "card", "phone"],
        ),
        (
            "Forget every 4242, the phone and the card too, except the gym.",
            (*_ENGLISH, "gym"),
            ["gym", "locker"],
        ),
        (
            "Forget every 4242, also the phone and the card, but keep the gym.",
            (*_ENGLISH, "gym"),
            ["gym", "locker"],
        ),
        (
            "Forget every 4242, keep the card, the phone and I are done too.",
            (*_ENGLISH, "badge"),
            ["badge", "card", "locker", "phone"],
        ),
        (
            "Oublie tous les 4242 sauf la carte, mon téléphone aussi.",
            _FRENCH,
            ["carte", "telephone"],
        ),
        (
            "Vergiss alle 4242, behalte die Karte, mein Handy auch.",
            _GERMAN,
            ["handy", "karte"],
        ),
    ],
)
async def test_a_word_for_all_a_keep_clause_and_an_adding_clause_keep_what_the_keep_reaches(
    query: str, ids: tuple[str, ...], left: list[str]
) -> None:
    assert (await _forget(query, *ids))[1] == left


@pytest.mark.parametrize(
    ("phone", "query", "kept"),
    [
        ("0721 5554242", "Forget every 4242 except the card.", ["card", "phone"]),
        ("0721 555 4242", "Forget every 4242 except the card.", ["card"]),
        ("0721 555 4242", "Forget 4242, except the card.", ["card", "phone"]),
        ("0721 555 4242", "Forget everything about 4242 except the card.", ["card", "phone"]),
    ],
)
def test_the_reader_lists_a_last_group_only_beside_a_word_for_all(
    phone: str, query: str, kept: list[str]
) -> None:
    texts = {
        "card": _ROWS["card"],
        "phone": f"User: Remember that my phone is {phone}.\nAssistant: Noted.",
    }
    rows = [
        MemoryRecord(id=name, text=text, embedding=(1.0, 0.0), at=_AT)
        for name, text in texts.items()
    ]
    assert [row.id for row in unnamed(rows, "4242", query)] == kept
