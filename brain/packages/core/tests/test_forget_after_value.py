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
from cortex_core.forget_clauses import after_value
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
_CARD = frozenset({"card"})


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


@pytest.mark.parametrize("phrase", [" though not the card", ", the card not"])
async def test_a_row_named_after_every_value_beside_a_negation_is_kept_and_shown(
    phrase: str,
) -> None:
    card, left = await _forget(f"Forget all 4242{phrase}.", *_ENGLISH)
    assert left == ["card"]
    assert card is not None
    listed, kept = card.split(KEPT_LINE)
    assert "these 2 remembered exchanges" in listed
    assert "4111 1111 1111 4242" in kept
    assert "4111 1111 1111 4242" not in listed


@pytest.mark.parametrize(
    ("query", "ids"),
    [
        ("Forget 4242 apart from the card.", _ENGLISH),
        ("Forget 4242 not the card.", _ENGLISH),
        ("Șterge toate 4242 în afară de card.", _ROMANIAN),
        ("Șterge toate 4242 cu excepția cardului.", _ROMANIAN),
        ("Forget 4242 that I texted from my phone.", ("locker", "phone")),
        ("Forget 4242, it is the end of my phone number.", ("locker", "phone")),
    ],
)
async def test_the_only_row_a_message_names_after_the_value_in_unread_words_is_kept(
    query: str, ids: tuple[str, ...]
) -> None:
    card, left = await _forget(query, *ids)
    assert left == sorted(ids)
    assert card is None


@pytest.mark.parametrize(
    ("query", "ids", "left"),
    [
        ("Forget the card 4242, the phone and the locker too.", _ENGLISH, []),
        ("Forget 4242, and the phone.", _ENGLISH, ["card"]),
        ("Forget all 4242 on the card.", _ENGLISH, ["locker", "phone"]),
        ("Forget all 4242, the card too.", _ENGLISH, []),
        ("Forget every card ending 4242.", _ENGLISH, ["locker", "phone"]),
        ("Forget 4242 on the card.", _ENGLISH, ["locker", "phone"]),
        ("Forget 4242 from my card.", _ENGLISH, ["locker", "phone"]),
        ("Forget 4242, my card.", _ENGLISH, ["locker", "phone"]),
        ("Forget 4242, the code on my card.", _ENGLISH, ["locker", "phone"]),
        ("Forget 4242, only the card.", _ENGLISH, ["locker", "phone"]),
        ("Forget 4242, that is my card.", _ENGLISH, ["locker", "phone"]),
        ("Forget 4242, I mean the card.", _ENGLISH, ["locker", "phone"]),
        ("Forget 4242 and forget the card.", _ENGLISH, ["locker", "phone"]),
        ("Forget all 4242, please forget the card.", _ENGLISH, []),
        ("Forget the locker 4242 but the card too.", _ENGLISH, ["phone"]),
        ("Forget 4242, the card and keep my phone.", _ENGLISH, ["locker", "phone"]),
        ("Forget the locker code 4242 and my phone number ending 4242.", _ENGLISH, ["card"]),
        ("Oublie le 4242 de ma carte.", _FRENCH, ["casier", "telephone"]),
        ("Vergiss 4242 auf der Karte.", _GERMAN, ["handy", "spind"]),
        ("Olvida el 4242 de mi tarjeta.", _SPANISH, ["gimnasio", "telefono"]),
        ("Șterge 4242 de pe card.", _ROMANIAN, ["dulap", "telefonul"]),
    ],
)
async def test_a_row_named_after_the_value_in_words_a_reader_reads_is_still_deleted(
    query: str, ids: tuple[str, ...], left: list[str]
) -> None:
    _, rows = await _forget(query, *ids)
    assert rows == left


async def test_a_word_of_the_reply_of_a_row_names_no_row_after_the_value() -> None:
    _, left = await _forget("Forget the locker code 4242, we noted it on the card.", *_ENGLISH)
    assert left == ["card", "phone"]


@pytest.mark.parametrize(
    ("query", "after"),
    [
        ("Forget all 4242 apart from the card.", ["apart", "from", "the", "card"]),
        ("Forget all 4242, leave the card.", ["leave", "the", "card"]),
        ("Forget all 4242 on the card, I need the card.", ["need", "the", "card"]),
        ("Forget all 4242, the card not.", ["the", "card", "not"]),
        ("Forget all 4242 of my old card.", ["old", "card"]),
        ("Forget all 4242 save the card and forget it now.", ["save", "the", "card", "and"]),
        ("Forget all 4242 on the card.", []),
        ("Forget all 4242 apart from the gym.", []),
        ("Forget all 4242 apart from the card too.", []),
        ("Forget all 4242 apart from the card as well.", []),
        ("Forget my card 4242 but keep Anna's card.", []),
        ("Leave the card, forget all 1234.", []),
        ("Forget 12 and 4242 or 77 on the card.", []),
    ],
)
def test_after_value_reads_the_words_that_may_ask_to_keep_a_row(
    query: str, after: list[str]
) -> None:
    assert after_value(query, "4242", _CARD) == after
