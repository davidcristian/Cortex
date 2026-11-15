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
from cortex_core.forget_clauses import (
    ADDITION,
    EXCEPTION,
    LIMIT,
    UNREAD,
    before_value,
    beside,
)
from cortex_core.forget_unnamed import KEPT_LINE
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
_SPANISH = ("gimnasio", "tarjeta", "telefono")
_ROMANIAN = ("dulap", "cardul", "telefonul")
_CODES = ("locker", "gym")
_CARD = frozenset({"card"})
_MINUS = frozenset({"minus"})


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


@pytest.mark.parametrize(
    ("query", "ids"),
    [
        ("Forget all 4242, card stays.", _ENGLISH),
        ("Forget all 4242, leave the card as well.", _ENGLISH),
        ("Forget all 4242, the card I still need.", _ENGLISH),
        ("Forget all 4242, my card remains.", _ENGLISH),
        ("Forget all 4242, the card is to stay.", _ENGLISH),
        ("Forget 4242, card stays.", _ENGLISH),
        ("Forget all 4242 but only the card.", _ENGLISH),
        ("Forget every 4242 but just the card.", _ENGLISH),
        ("Forget 4242 but only the card.", _ENGLISH),
        ("Forget the card 4242 but only the card.", _ENGLISH),
        ("Forget all 4242 but the card only.", _ENGLISH),
        ("Forget all 4242 but not only the card.", _ENGLISH),
        ("Forget all 4242 apart from the card.", _ENGLISH),
        ("Forget all 4242 other than the card.", _ENGLISH),
        ("Forget all 4242 besides the card.", _ENGLISH),
        ("Forget all 4242 save the card.", _ENGLISH),
        ("Forget all 4242 aside from the card.", _ENGLISH),
        ("Forget all 4242 with the exception of the card.", _ENGLISH),
        ("Forget all 4242 without the card.", _ENGLISH),
        ("Forget all 4242 barring the card.", _ENGLISH),
        ("Forget all 4242 including the card.", _ENGLISH),
        ("Forget all 4242, leave the card.", _ENGLISH),
        ("Forget all 4242, I still need the card.", _ENGLISH),
        ("Forget all 4242, spare my card.", _ENGLISH),
        ("Forget all 4242 apart from the card 4242.", _ENGLISH),
        ("Forget all 4242 apart from the card, and do it now.", _ENGLISH),
        ("Forget all 4242 apart from the card and the phone.", _ENGLISH),
        ("Forget every 4242, the card first.", _ENGLISH),
        ("Forget 4242 on the card please.", _ENGLISH),
        ("Verwijder alle 4242 behalve de card.", _ENGLISH),
        ("Vergiss alle 4242, die Karte brauche ich noch.", _GERMAN),
        ("Vergiss alle 4242 bis auf die Karte.", _GERMAN),
        ("Vergiss alle 4242 ohne die Karte.", _GERMAN),
        ("Oublie tous les 4242, la carte reste.", _FRENCH),
        ("Oublie tous les 4242 à part la carte.", _FRENCH),
        ("Oublie tous les 4242 hors la carte.", _FRENCH),
        ("Oublie le code 4242 du casier que j'ai envoyé par téléphone.", ("casier", "telephone")),
        ("Olvida 4242, la tarjeta se queda.", _SPANISH),
        ("Olvida todas las 4242 aparte de la tarjeta.", _SPANISH),
        ("Uită 4242, cardul rămâne.", _ROMANIAN),
        ("Forget all 4242. The card, though, stays.", _ENGLISH),
        ("Forget all 4242, the card, no.", _ENGLISH),
        ("Forget 4242, the card, I need it.", _ENGLISH),
        ("Forget all 4242 on the card, thanks.", _ENGLISH),
    ],
)
async def test_a_row_named_beside_the_value_in_a_role_no_reader_reads_keeps_every_row(
    query: str, ids: tuple[str, ...]
) -> None:
    card, left = await _forget(query, *ids)
    assert left == sorted(ids)
    assert card is None


@pytest.mark.parametrize(
    ("query", "ids", "left"),
    [
        ("Forget all 4242 on the card.", _ENGLISH, ["locker", "phone"]),
        ("Forget all 4242, only the card.", _ENGLISH, ["locker", "phone"]),
        ("Forget all 4242 only on the card.", _ENGLISH, ["locker", "phone"]),
        ("Forget all 4242, just the card and the phone.", _ENGLISH, ["locker"]),
        ("Forget all 4242, the locker one.", _ENGLISH, ["card", "phone"]),
        ("Vergiss alle 4242 auf der Karte.", _GERMAN, ["handy", "spind"]),
        ("Oublie tous les 4242 sur la carte.", _FRENCH, ["casier", "telephone"]),
        ("Olvida todas las 4242 de la tarjeta.", _SPANISH, ["gimnasio", "telefono"]),
    ],
)
async def test_a_forget_of_every_value_limited_to_a_row_keeps_the_other_rows(
    query: str, ids: tuple[str, ...], left: list[str]
) -> None:
    card, rows = await _forget(query, *ids)
    assert rows == left
    assert card is not None
    assert KEPT_LINE in card


@pytest.mark.parametrize(
    ("query", "ids", "left"),
    [
        ("Forget 4242.", _CODES, []),
        ("Forget all 4242.", _ENGLISH, []),
        ("Forget all my 4242 codes.", _CODES, []),
        ("Forget the card 4242.", _ENGLISH, ["locker", "phone"]),
        ("Forget every card ending 4242.", _ENGLISH, ["locker", "phone"]),
        ("Forget 4242 on the card.", _ENGLISH, ["locker", "phone"]),
        ("Forget all 4242 except the card.", _ENGLISH, ["card"]),
        ("Forget all 4242 but the card.", _ENGLISH, ["card"]),
        ("Forget all 4242 minus the card.", _ENGLISH, ["card"]),
        ("Forget the card 4242, the phone and the locker too.", _ENGLISH, []),
        ("Forget all 4242, the card too.", _ENGLISH, []),
        ("Forget all 4242, also the phone.", _ENGLISH, []),
        ("Forget all 4242 and the phone.", _ENGLISH, []),
        ("Forget all 4242, the card as well.", _ENGLISH, []),
        ("Forget the locker 4242 but the card too.", _ENGLISH, ["phone"]),
        ("Forget the locker code 4242 and my phone number ending 4242.", _ENGLISH, ["card"]),
        ("Forget the locker 4242, card stays.", _ENGLISH, ["card", "phone"]),
        ("Forget the locker code 4242 and the card, I texted both.", _ENGLISH, ["card", "phone"]),
        ("Forget all 4242, please, only the card.", _ENGLISH, ["locker", "phone"]),
        ("Oublie le code 4242 du casier, la carte reste.", _FRENCH, ["carte", "telephone"]),
    ],
)
async def test_a_row_the_message_asks_for_in_words_a_reader_reads_is_still_deleted(
    query: str, ids: tuple[str, ...], left: list[str]
) -> None:
    assert (await _forget(query, *ids))[1] == left


@pytest.mark.parametrize(
    ("query", "role"),
    [
        ("Forget all 4242 on the card.", LIMIT),
        ("Forget all 4242, that is my card.", LIMIT),
        ("Forget all 4242, the card one.", LIMIT),
        ("Forget all 4242, the card too.", ADDITION),
        ("Forget all 4242, also the card.", ADDITION),
        ("Forget all 4242, the card as well.", ADDITION),
        ("Forget all 4242 and the card.", ADDITION),
        ("Forget all 4242 but the card too.", ADDITION),
        ("Forget all 4242 but the card.", EXCEPTION),
        ("Forget all 4242 but only the card.", UNREAD),
        ("Forget all 4242 but on the card.", UNREAD),
        ("Forget all 4242, card stays.", UNREAD),
        ("Forget all 4242, leave the card as well.", UNREAD),
        ("Forget all 4242, the card one stays.", UNREAD),
        ("Forget all 4242, the card, though, stays.", UNREAD),
        ("Forget all 4242 on the card, I need it.", UNREAD),
        ("Forget all 4242, please, only the card.", LIMIT),
        ("Forget all 4242 on the card, and 4242 too.", LIMIT),
    ],
)
def test_beside_reads_the_role_of_a_row_named_after_the_value(query: str, role: str) -> None:
    roles = beside(query, "4242", _CARD, _MINUS)
    assert {name: words for name, words in roles.items() if words} == {role: {"card"}}


@pytest.mark.parametrize(
    "query",
    [
        "Forget all 4242.",
        "Forget all 4242 quickly.",
        "Forget the card 4242.",
        "Forget all 4242 except the card.",
        "Forget all 4242, keep the card.",
        "Forget all 4242, the card not.",
        "Forget all 4242 minus the card.",
        "Forget the card.",
    ],
)
def test_beside_reads_no_role_without_a_row_named_after_the_value_outside_a_keep_clause(
    query: str,
) -> None:
    assert not any(beside(query, "4242", _CARD, _MINUS).values())


def test_before_value_reads_the_words_of_each_clause_before_its_last_value() -> None:
    query = "Forget the locker 4242 and my phone ending 4242 now, card stays, I mean 4242."
    words = "forget the locker 4242 and my phone ending i mean"
    assert before_value(query, "4242") == words.split()
    assert before_value("Forget the card.", "4242") == []
