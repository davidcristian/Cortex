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
from cortex_core.forget_clauses import asking
from cortex_core.forget_inside import INSIDE_LINE
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 13, 6, 0, 0, tzinfo=UTC)
_ROWS = {
    "locker": "User: Remember that my locker code is 4242.\nAssistant: Noted.",
    "casier": "User: Retiens que le code du casier est 4242.\nAssistant: Noté.",
    "spind": "User: Merke dir, der Code vom Spind ist 4242.\nAssistant: Notiert.",
    "gimnasio": "User: Recuerda que el código del gimnasio es 4242.\nAssistant: Anotado.",
    "gym": "User: Remember that my gym code is 4242.\nAssistant: Noted.",
    "phone": "User: Remember that my phone is 0721 555 4242.\nAssistant: Noted.",
    "card": "User: Remember that my card is 4111 1111 1111 4242.\nAssistant: Noted.",
}


async def _forget(query: str, *ids: str) -> tuple[str | None, str, list[str]]:
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
    result = await tool.invoke(call)
    left = sorted(hit.record.id for hit in await store.search((1.0, 0.0), k=10))
    return card, result.content, left


@pytest.mark.parametrize(
    ("query", "ids"),
    [
        ("Forget the locker code 4242 that I texted from my phone.", ("locker", "phone")),
        ("Oublie le code 4242 du casier que j'ai envoyé par téléphone.", ("casier", "phone")),
        ("Oublie le code 4242 du casier, il est noté sur la carte du parc.", ("casier", "card")),
        (
            "Vergiss den Code 4242 vom Spind, er steht auf meiner Karte fürs Konzert.",
            ("spind", "card"),
        ),
        ("Olvida el código 4242 del gimnasio, lo escribí en la tarjeta.", ("gimnasio", "card")),
        ("Forget my gym code 4242, the one written on the birthday card.", ("gym", "card")),
        ("I texted it from my phone: forget the locker code 4242.", ("locker", "phone")),
    ],
)
async def test_a_row_named_only_in_a_remark_about_the_value_is_kept_and_shown(
    query: str, ids: tuple[str, ...]
) -> None:
    card, result, left = await _forget(query, *ids)
    assert left == [ids[1]]
    assert card is not None
    assert card.split(INSIDE_LINE)[1].count("4242") == 1
    assert "1 other remembered exchanges contain that text only inside a longer value" in result


@pytest.mark.parametrize(
    ("query", "ids", "left"),
    [
        ("Forget my phone and card numbers ending 4242.", ("gym", "phone", "card"), ["gym"]),
        ("Forget the locker code 4242 and my phone number ending 4242.", ("locker", "phone"), []),
        ("Forget the locker code 4242, and the card one too.", ("locker", "card"), []),
        ("Forget the locker code 4242 and the phone that ends in 4242.", ("locker", "phone"), []),
        (
            "Forget that my locker code is 4242 and my phone is 0721 555 4242.",
            ("locker", "phone"),
            [],
        ),
        ("Forget the locker code 4242 and the card, I texted both.", ("locker", "card"), []),
        ("Forget 4242 that I texted from my phone.", ("locker", "phone"), ["locker"]),
        ("Forget 4242, it is the end of my phone number.", ("locker", "phone"), ["locker"]),
    ],
)
async def test_a_row_named_where_the_message_asks_to_forget_is_still_listed(
    query: str, ids: tuple[str, ...], left: list[str]
) -> None:
    card, _, rows = await _forget(query, *ids)
    assert card is not None
    assert INSIDE_LINE not in card
    assert rows == left


@pytest.mark.parametrize(
    ("query", "text", "asked"),
    [
        ("Forget the code 4242 that I sent.", "4242", "forget the code 4242"),
        ("Forget that my code is 4242.", "4242", "forget that my code is 4242"),
        ("Forget 4242, it is on my card.", "4242", "forget 4242"),
        ("Forget 4242, and the card.", "4242", "forget 4242 and the card"),
        ("Forget 4242, not the card.", "4242", "forget 4242 not the card"),
        ("It is on my card, 0721 555 4242.", "0721 555 4242", "0721 555 4242"),
        ("Forget the code 42 42 that I sent.", "4242", "forget the code 42 42 that i sent"),
        ("Forget my code.", "", "forget my code"),
    ],
)
def test_asking_reads_the_message_less_each_remark(query: str, text: str, asked: str) -> None:
    assert asking(query, text) == asked
