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
from cortex_core.forget_keep_named import forget_named
from cortex_core.forget_unnamed import KEPT_ALL
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 15, 8, 0, 0, tzinfo=UTC)
_ROWS = {
    "gym": "User: Remember that my gym code is 4242.\nAssistant: Noted.",
    "locker": "User: Remember that my locker code is 4242.\nAssistant: Noted.",
    "phone": "User: Remember that my phone is 0721 555 4242.\nAssistant: Noted.",
    "card": "User: Remember that my card is 4111 1111 1111 4242.\nAssistant: Noted.",
    "casier": "User: Retiens que le code du casier est 4242.\nAssistant: Noté.",
    "carte": "User: Retiens que ma carte est 4111 1111 1111 4242.\nAssistant: Noté.",
}
_TWO = ("card", "gym")
_THREE = ("locker", "card", "phone")


async def _store(*ids: str) -> InMemoryMemoryStore:
    store = InMemoryMemoryStore()
    for i, name in enumerate(ids):
        at = _AT + timedelta(minutes=i)
        record = MemoryRecord(
            id=name, text=_ROWS[name], embedding=(1.0, 0.0), at=at, session_id="chat-a"
        )
        await store.add(record)
    return store


def _call(query: str, text: str, call_id: str = "c1") -> ToolCall:
    stamp = TurnStamp(session_id="chat-new", turn_id="t1", query=query)
    return ToolCall(id=call_id, name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text}, stamp=stamp)


async def _left(store: InMemoryMemoryStore) -> list[str]:
    return sorted(hit.record.id for hit in await store.search((1.0, 0.0), k=10))


async def _forget(query: str, text: str, *ids: str) -> tuple[str, list[str]]:
    store = await _store(*ids)
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    call = _call(query, text)
    await tool.card(call)
    result = await tool.invoke(call)
    return result.content, await _left(store)


@pytest.mark.parametrize(
    ("query", "text", "ids"),
    [
        ("Forget my gym code.", "card", _TWO),
        ("Forget my gym code.", "my card", _TWO),
        ("Forget all codes but my card.", "phone", _THREE),
        ("Forget my locker code.", "phone", _THREE),
        ("Forget 4242, the card too.", "phone", _THREE),
        ("Forget my locker code but keep my card.", "phone", _THREE),
        ("Oublie le code du casier.", "carte", ("casier", "carte")),
    ],
)
async def test_a_call_naming_a_row_beside_a_message_naming_another_stored_row_keeps_it(
    query: str, text: str, ids: tuple[str, ...]
) -> None:
    content, left = await _forget(query, text, *ids)

    assert left == sorted(ids)
    assert content == f"{KEPT_ALL}."


@pytest.mark.parametrize(
    ("query", "text", "ids", "left"),
    [
        ("Forget what I just told you.", "card", _TWO, ["gym"]),
        ("Please do it.", "card", _TWO, ["gym"]),
        ("Forget that.", "card", _TWO, ["gym"]),
        ("Yes, delete it please.", "card", _TWO, ["gym"]),
        ("Forget what you noted.", "card", _TWO, ["gym"]),
        ("Forget my gym code.", "gym", _TWO, ["card"]),
        ("Forget my gym code.", "gym code", _TWO, ["card"]),
        ("Forget my gym code and my card.", "card", _TWO, ["gym"]),
        ("Forget everything but my card.", "phone", _THREE, ["card", "locker"]),
        ("Forget my locker code and 0721 555 4242.", "0721 555 4242", _THREE, ["card", "locker"]),
        (
            "Forget everything, the card too, the phone too.",
            "locker code",
            _THREE,
            ["card", "phone"],
        ),
        (
            "Forget everything and the card, the phone too.",
            "locker code",
            _THREE,
            ["card", "phone"],
        ),
    ],
)
async def test_a_call_naming_a_row_the_message_names_or_beside_no_named_row_deletes_it(
    query: str, text: str, ids: tuple[str, ...], left: list[str]
) -> None:
    assert (await _forget(query, text, *ids))[1] == left


async def test_a_later_call_keeps_a_row_beside_the_named_row_an_earlier_call_deleted() -> None:
    store = await _store(*_TWO)
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    for call_id, text in (("c1", "gym code"), ("c2", "card")):
        call = _call("Forget my gym code.", text, call_id)
        await tool.card(call)
        await tool.invoke(call)

    assert await _left(store) == ["card"]


@pytest.mark.parametrize(
    ("query", "named"),
    [
        ("Forget my gym code.", ["gym"]),
        ("Forget my gym code and my card.", ["card", "gym"]),
        ("Forget my car.", []),
        ("Forget what you noted.", []),
        ("Forget everything but my card.", []),
        ("Forget that.", []),
    ],
)
async def test_the_rows_a_forget_part_names_are_those_a_whole_word_of_their_request_names(
    query: str, named: list[str]
) -> None:
    store = await _store(*_TWO)

    rows = await forget_named(store, GLOBAL_MEMORY_SCOPE, _call(query, "card"), 5, ())

    assert sorted({row.id for row in rows}) == named
