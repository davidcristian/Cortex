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
from cortex_core.forget_value_added import adds_to_value
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 23, 6, 0, 0, tzinfo=UTC)
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
    "dulap": "User: Ține minte că codul de la dulap este 4242.\nAssistant: Notat.",
    "cardul": "User: Ține minte că cardul meu este 4111 1111 1111 4242.\nAssistant: Notat.",
    "telefonul": "User: Ține minte că telefonul meu este 0721 555 4242.\nAssistant: Notat.",
}
_ENGLISH = ("locker", "card", "phone")
_FRENCH = ("casier", "carte", "telephone")
_GERMAN = ("spind", "karte", "handy")
_ROMANIAN = ("dulap", "cardul", "telefonul")
_NAMED = frozenset({"card", "phone", "locker", "code"})


async def _left(query: str, ids: tuple[str, ...], text: str = "4242") -> list[str]:
    store = InMemoryMemoryStore()
    for i, name in enumerate(ids):
        at = _AT + timedelta(minutes=i)
        record = MemoryRecord(
            id=name, text=_ROWS[name], embedding=(1.0, 0.0), at=at, session_id="chat-a"
        )
        await store.add(record)
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(session_id="chat-new", turn_id="t1", query=query)
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text}, stamp=stamp)
    await tool.card(call)
    await tool.invoke(call)
    return sorted(hit.record.id for hit in await store.search((1.0, 0.0), k=10))


@pytest.mark.parametrize(
    ("query", "ids", "left"),
    [
        ("Forget 4242, the card too.", _ENGLISH, ["phone"]),
        ("Forget 4242 and the card.", _ENGLISH, ["phone"]),
        ("Forget 4242, the card as well.", _ENGLISH, ["phone"]),
        ("Forget 4242, also my card.", _ENGLISH, ["phone"]),
        ("Forget 4242, the card too, the phone too.", _ENGLISH, []),
        ("Oublie 4242, la carte aussi.", _FRENCH, ["telephone"]),
        ("Vergiss 4242, die Karte auch.", _GERMAN, ["handy"]),
        ("Uită 4242 și cardul.", _ROMANIAN, ["telefonul"]),
    ],
)
async def test_a_row_added_after_a_value_alone_also_lists_each_row_holding_it_whole(
    query: str, ids: tuple[str, ...], left: list[str]
) -> None:
    assert await _left(query, ids) == left


async def test_a_row_added_after_a_value_alone_is_listed_by_its_own_name_too() -> None:
    assert await _left("Forget 4242, the card too.", _ENGLISH, "locker code") == ["card", "phone"]


@pytest.mark.parametrize(
    ("query", "left"),
    [
        ("Forget the card 4242, my phone as well.", ["locker"]),
        ("Forget 4242, the card stays.", ["card", "locker", "phone"]),
        ("Forget 4242, my card.", ["locker", "phone"]),
        ("Forget 4242, also the card only on the card.", ["locker", "phone"]),
        ("Please forget 4242, the card too.", ["locker", "phone"]),
        ("Forget 4242, the card too, keep the locker.", ["locker", "phone"]),
    ],
)
async def test_a_value_beside_a_named_row_or_an_unread_word_keeps_what_it_kept(
    query: str, left: list[str]
) -> None:
    assert await _left(query, _ENGLISH) == left


@pytest.mark.parametrize(
    ("query", "value"),
    [
        ("Forget 4242, the card too.", "4242"),
        ("Forget 12 34, my phone as well.", "12 34"),
        ("Forget 4242, or the phone.", "4242"),
    ],
)
def test_adds_to_value_reads_a_value_then_only_words_adding_a_row(query: str, value: str) -> None:
    assert adds_to_value(query, value, _NAMED)


@pytest.mark.parametrize(
    ("query", "value"),
    [
        ("Forget the card, the phone too.", "card"),
        ("Forget 4242, the card too.", "9999"),
        ("Forget 4242, the card too.", ""),
        ("Forget 4242.", "4242"),
        ("Forget 4242 too.", "4242"),
        ("Forget 4242, the card.", "4242"),
        ("Forget 4242 on the card, the phone too.", "4242"),
        ("Forget the 4242 of the card too.", "4242"),
        ("4242, the card too.", "4242"),
    ],
)
def test_adds_to_value_reads_no_other_words_after_a_value(query: str, value: str) -> None:
    assert not adds_to_value(query, value, _NAMED)
