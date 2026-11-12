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
from cortex_core.forget_inside import inside
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 12, 3, 0, 0, tzinfo=UTC)
_CARD = "User: Remember that my card is 4111 1111 1111 4242.\nAssistant: Noted."
_GYM = "User: Remember that my gym code is 4242.\nAssistant: Noted."
_ORDERS = [("card", "gym"), ("gym", "card")]
_ROWS = {"card": _CARD, "gym": _GYM}


async def _forget(
    query: str, texts: tuple[str, ...], order: tuple[str, ...], chat: str
) -> list[str]:
    store = InMemoryMemoryStore()
    for index, name in enumerate(order):
        at = _AT + timedelta(minutes=index)
        record = MemoryRecord(
            id=name, text=_ROWS[name], embedding=(1.0, 0.0), at=at, session_id="chat-a"
        )
        await store.add(record)
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(session_id=chat, turn_id="t1", query=query)
    for index, text in enumerate(texts):
        call = ToolCall(
            id=f"c{index}", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text}, stamp=stamp
        )
        await tool.card(call)
        await tool.invoke(call)
    return sorted(hit.record.id for hit in await store.search((1.0, 0.0), k=10))


@pytest.mark.parametrize("first", ["4242", "gym code"])
@pytest.mark.parametrize("order", _ORDERS)
async def test_a_second_call_of_the_turn_keeps_the_card_the_first_call_kept(
    first: str, order: tuple[str, ...]
) -> None:
    left = await _forget("Forget my gym code 4242.", (first, "4242"), order, "chat-new")
    assert left == ["card"]


@pytest.mark.parametrize("first", ["4242", "gym code"])
@pytest.mark.parametrize("order", _ORDERS)
async def test_a_second_call_lists_the_card_a_message_names(
    first: str, order: tuple[str, ...]
) -> None:
    query = "Forget my gym code and the card ending in 4242."
    assert await _forget(query, (first, "4242"), order, "chat-new") == []


def test_inside_reads_a_deleted_row_holding_the_text_whole_on_the_card() -> None:
    card = MemoryRecord(id="card", text=_CARD, embedding=(1.0, 0.0), at=_AT)
    assert inside([card], "4242", "Forget my gym code 4242.", (_GYM,)) == {"card"}
    query = "Forget my gym code and the card ending in 4242."
    assert inside([card], "4242", query, (_GYM,)) == frozenset()


@pytest.mark.parametrize(
    "query",
    [
        "Forget everything with 4242.",
        "Forget every 4242.",
        "Forget all of 4242.",
        "Forget 4242 everywhere.",
    ],
)
@pytest.mark.parametrize("order", _ORDERS)
@pytest.mark.parametrize("chat", ["chat-a", "chat-new"])
async def test_a_forget_of_every_row_holding_the_code_lists_the_card(
    query: str, order: tuple[str, ...], chat: str
) -> None:
    assert await _forget(query, ("4242",), order, chat) == []


@pytest.mark.parametrize(
    ("query", "left"),
    [
        ("Forget every gym code 4242.", ["card"]),
        ("Forget the code 4242 everywhere.", ["card"]),
        ("Vergiss den Fahrradcode 4242 überall.", ["card", "gym"]),
        ("Forget everything about my gym, 4242.", ["card"]),
        ("Forget every 4242 except the card.", ["card", "gym"]),
        ("Forget every 4242 but keep the card.", ["card", "gym"]),
        ("Forget my gym code 4242, all of it.", ["card"]),
    ],
)
@pytest.mark.parametrize("order", _ORDERS)
async def test_a_word_for_all_away_from_the_code_keeps_the_card(
    query: str, left: list[str], order: tuple[str, ...]
) -> None:
    assert await _forget(query, ("4242",), order, "chat-new") == left


@pytest.mark.parametrize("texts", [("4242",), ("4242", "4242")])
@pytest.mark.parametrize("query", ["Forget what I just told you.", "Forget my bank details."])
@pytest.mark.parametrize("order", _ORDERS)
async def test_a_second_call_keeps_the_older_row_after_the_newest_is_deleted(
    texts: tuple[str, ...], query: str, order: tuple[str, ...]
) -> None:
    assert await _forget(query, texts, order, "chat-a") == [order[0]]
