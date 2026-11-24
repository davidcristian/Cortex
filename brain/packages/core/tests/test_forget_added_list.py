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
from cortex_core.forget_remarks import asking
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 15, 6, 0, 0, tzinfo=UTC)
_ROWS = {
    "locker": "User: Remember that my locker code is 4242.\nAssistant: Noted.",
    "gym": "User: Remember that my gym code is 4242.\nAssistant: Noted.",
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


async def _left(query: str, *ids: str) -> list[str]:
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
        ("Forget the card 4242, the phone and the locker too.", _ENGLISH),
        ("Forget the card 4242, my phone and my locker too.", _ENGLISH),
        ("Forget the locker code 4242, the phone and the card too.", _ENGLISH),
        ("Forget the locker code 4242, also my phone and my card.", _ENGLISH),
        ("Forget the locker code 4242, my phone and my card as well.", _ENGLISH),
        ("Forget the locker code 4242, the phone and the card one too.", _ENGLISH),
        ("Forget the card 4242, the phone and the locker and the gym too.", (*_ENGLISH, "gym")),
        ("Oublie le code 4242 du casier, mon téléphone et la carte aussi.", _FRENCH),
        ("Vergiss den Code 4242 vom Spind, mein Handy und die Karte auch.", _GERMAN),
    ],
)
async def test_a_clause_adding_a_list_of_rows_lists_each_row(
    query: str, ids: tuple[str, ...]
) -> None:
    assert await _left(query, *ids) == []


@pytest.mark.parametrize(
    ("query", "ids", "left"),
    [
        ("Forget the card 4242, the phone and I are done too.", _ENGLISH, ["locker", "phone"]),
        ("Forget the locker code 4242, the phone or the card too.", _ENGLISH, ["card", "phone"]),
        ("Forget the locker code 4242, the phone and card too.", _ENGLISH, ["card", "phone"]),
        (
            "Forget the locker code 4242, the phone and the card and too.",
            _ENGLISH,
            ["card", "phone"],
        ),
        (
            "Forget the locker code 4242, the phone and the passport too.",
            _ENGLISH,
            ["card", "phone"],
        ),
        ("Forget the locker code 4242, the phone and that card too.", _ENGLISH, ["card", "phone"]),
        (
            "Oublie le code 4242 du casier, mon téléphone ou la carte aussi.",
            _FRENCH,
            ["carte", "telephone"],
        ),
        ("Oublie la carte 4242, mon téléphone et moi aussi.", _FRENCH, ["casier", "telephone"]),
        (
            "Vergiss den Code 4242 vom Spind, mein Handy oder die Karte auch.",
            _GERMAN,
            ["handy", "karte"],
        ),
        ("Vergiss die Karte 4242, mein Handy und ich auch.", _GERMAN, ["handy", "spind"]),
        (
            "Olvida el código 4242 del gimnasio, mi teléfono y la tarjeta también.",
            ("gimnasio", "tarjeta", "telefono"),
            ["tarjeta", "telefono"],
        ),
        (
            "Șterge codul 4242 de la dulap, telefonul și cardul de asemenea.",
            ("dulap", "cardul", "telefonul"),
            ["cardul", "telefonul"],
        ),
    ],
)
async def test_a_clause_with_a_joining_word_that_lists_no_rows_stays_a_remark(
    query: str, ids: tuple[str, ...], left: list[str]
) -> None:
    assert await _left(query, *ids) == left


@pytest.mark.parametrize(
    ("query", "ids", "left"),
    [
        ("Forget the card 4242, keep the locker, my phone too.", _ENGLISH, ["locker", "phone"]),
        (
            "Forget the card 4242, keep the locker, my phone and my gym too.",
            (*_ENGLISH, "gym"),
            ["gym", "locker", "phone"],
        ),
        (
            "Forget the card 4242, the phone and the locker I keep too.",
            _ENGLISH,
            ["locker", "phone"],
        ),
        ("Forget the locker code 4242, the phone and keep the card too.", _ENGLISH, ["card"]),
        (
            "Oublie le code 4242 du casier, garde la carte, mon téléphone et ma carte aussi.",
            _FRENCH,
            ["carte", "telephone"],
        ),
        (
            "Vergiss den Code 4242 vom Spind, behalte die Karte, mein Handy und die Karte auch.",
            _GERMAN,
            ["handy", "karte"],
        ),
    ],
)
async def test_a_list_beside_a_keep_clause_keeps_the_rows_the_keep_clause_reaches(
    query: str, ids: tuple[str, ...], left: list[str]
) -> None:
    assert await _left(query, *ids) == left


@pytest.mark.parametrize(
    ("query", "named", "asked"),
    [
        (
            "Forget 4242, my phone and my gym too.",
            {"phone", "gym"},
            "forget 4242 my phone and my gym too",
        ),
        (
            "Forget 4242, also my phone and the gym one.",
            {"phone", "gym"},
            "forget 4242 also my phone and the gym one",
        ),
        (
            "Oublie 4242, mon téléphone et la carte aussi.",
            {"téléphone", "carte"},
            "oublie 4242 mon téléphone et la carte aussi",
        ),
        (
            "Vergiss 4242, mein Handy und die Karte auch.",
            {"handy", "karte"},
            "vergiss 4242 mein handy und die karte auch",
        ),
        ("Forget 4242, my phone and my gym too.", {"phone"}, "forget 4242"),
        ("Forget 4242, my phone or my gym too.", {"phone", "gym"}, "forget 4242"),
        ("Forget 4242, my phone and gym too.", {"phone", "gym"}, "forget 4242"),
        ("Forget 4242, my phone and old gym too.", {"phone", "gym"}, "forget 4242"),
        ("Forget 4242, my phone and my too.", {"phone", "gym"}, "forget 4242"),
        ("Forget 4242, my phone and too.", {"phone", "gym"}, "forget 4242"),
        ("Forget 4242, one and my phone too.", {"phone", "gym"}, "forget 4242"),
        ("Forget 4242, my phone and I too.", {"phone", "gym"}, "forget 4242"),
    ],
)
def test_asking_reads_a_list_only_when_every_item_names_a_row(
    query: str, named: set[str], asked: str
) -> None:
    assert asking(query, "4242", frozenset(named)) == asked
