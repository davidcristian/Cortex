import itertools
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
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 15, 9, 0, 0, tzinfo=UTC)
_ROWS = {
    "gym": "User: Remember that my gym code is 4242.\nAssistant: Noted.",
    "locker": "User: Remember that my locker code is 4242.\nAssistant: Noted.",
    "phone": "User: Remember that my phone is 0721 555 4242.\nAssistant: Noted.",
    "card": "User: Remember that my card is 4111 1111 1111 4242.\nAssistant: Noted.",
    "address": "User: Remember that my address is Elm Street.\nAssistant: Noted.",
    "telefon": "User: Merke dir, mein Telefon ist 0721 555 9999.\nAssistant: Notiert.",
}
_THREE = ("locker", "card", "phone")
_HEADS = ("Forget 4242", "Forget all 4242", "Forget the {row} 4242", "Forget 4242 on the {row}")
_TAILS = (
    " except the {row}",
    ", excluding the {row}",
    " apart from the {row}",
    " but the {row}",
    ", but not the {row}",
    ", keep the {row}",
    ". Keep the {row}",
    ", {row} stays",
    ", not the {row}",
    ", the {row} too",
    ", also the {row}",
    " and the {row}",
    ", only the {row}",
    " only on the {row}",
    " but only the {row}",
    ", just the {row}",
)
_TEXTS = ("locker code", "card", "phone", "code", "my locker", "remember that my card")


def _messages() -> list[str]:
    tails = ["", *(tail.format(row=row) for tail in _TAILS for row in _THREE)]
    pairs = itertools.product(_HEADS, tails)
    return [head.format(row="locker") + tail + "." for head, tail in pairs]


async def _deleted(
    query: str, text: str, ids: tuple[str, ...] = _THREE, said: str = ""
) -> set[str]:
    store = InMemoryMemoryStore()
    for i, name in enumerate(ids):
        at = _AT + timedelta(minutes=i)
        chat = "chat-new" if name == said else "chat-a"
        record = MemoryRecord(
            id=name, text=_ROWS[name], embedding=(1.0, 0.0), at=at, session_id=chat
        )
        await store.add(record)
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(session_id="chat-new", turn_id="t1", query=query)
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text}, stamp=stamp)
    await tool.card(call)
    await tool.invoke(call)
    left = {hit.record.id for hit in await store.search((1.0, 0.0), k=10)}
    return set(ids) - left


async def test_no_call_text_deletes_a_row_the_value_of_the_message_does_not() -> None:
    cases = [(query, text) for query in _messages() for text in _TEXTS]
    deleted = [(query, text, await _deleted(query, text)) for query, text in cases]
    permitted = {query: await _deleted(query, "4242") for query in _messages()}
    assert [case for case in deleted if not case[2] <= permitted[case[0]]] == []
    assert sum(len(rows) for _, _, rows in deleted) > len(_messages())


@pytest.mark.parametrize(
    ("query", "text"),
    [
        ("Forget all 4242 apart from the card.", "card"),
        ("Forget all 4242, card stays.", "card"),
        ("Forget all 4242, only the card.", "locker code"),
        ("Forget all 4242, only the card.", "phone"),
        ("Forget all 4242 but only the card.", "locker code"),
        ("Forget all 4242 but only the card.", "phone"),
        ("Forget the 4242 of my locker.", "phone"),
        ("Forget 4242, the card too.", "phone"),
        ("Forget 4242.", "card"),
        ("Forget 4242, address stays.", "address"),
    ],
)
async def test_a_call_naming_a_row_the_message_does_not_permit_deletes_nothing(
    query: str, text: str
) -> None:
    assert await _deleted(query, text, (*_THREE, "address")) == set()


@pytest.mark.parametrize(
    ("query", "text", "ids", "gone"),
    [
        ("Forget my gym code.", "gym code", ("gym", "card"), {"gym"}),
        ("Forget my code.", "gym code", ("gym", "card"), {"gym"}),
        ("Forget everything but my card.", "gym code", ("gym", "card"), {"gym"}),
        ("Forget all 4242 except the card.", "4242", _THREE, {"locker", "phone"}),
        ("Forget all 4242 except the card.", "locker code", _THREE, {"locker"}),
        ("Forget all 4242 except the card.", "phone", _THREE, {"phone"}),
        ("Forget all 4242, only the card.", "card", _THREE, {"card"}),
        ("Forget my locker code.", "locker code", _THREE, {"locker"}),
        ("Forget 4242 and my address.", "address", (*_THREE, "address"), {"address"}),
        ("Forget 4242 and my phone.", "Telefon", ("locker", "telefon"), {"telefon"}),
        ("Forget my address, the 9999 one.", "address", (*_THREE, "address"), {"address"}),
    ],
)
async def test_a_call_naming_a_row_the_message_permits_deletes_it(
    query: str, text: str, ids: tuple[str, ...], gone: set[str]
) -> None:
    assert await _deleted(query, text, ids) == gone


@pytest.mark.parametrize(
    "query",
    [
        "Forget that.",
        "Yes, forget it.",
        "Forget what I just told you.",
        "Forget my gym code.",
        "Forget the code.",
    ],
)
async def test_a_message_naming_no_stored_row_lists_what_the_call_names(query: str) -> None:
    assert await _deleted(query, "phone", ("card", "phone")) == {"phone"}
    assert await _deleted(query, "card", ("card", "phone"), said="card") == {"card"}
