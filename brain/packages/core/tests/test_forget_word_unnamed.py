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
from cortex_core.forget_results import forgot
from cortex_core.forget_unnamed import KEPT_LINE
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 13, 4, 20, 0, tzinfo=UTC)
_ROWS = {
    "gym": "User: Remember that my gym code is 4242.\nAssistant: Noted.",
    "bike": "User: Remember that my bike lock code is 7319.\nAssistant: Noted.",
    "shed": "User: Remember that the shed padlock code is also 4242.\nAssistant: Noted.",
    "card": "User: Remember that my card is 4111 1111 1111 4242.\nAssistant: Noted.",
    "card2": "User: Remember that my other card is 5500 0000 0000 4242.\nAssistant: Noted.",
}


async def _forget(query: str, text: str, *ids: str, chat: str) -> tuple[str | None, list[str]]:
    store = InMemoryMemoryStore()
    for i, name in enumerate(ids):
        at = _AT + timedelta(minutes=i)
        record = MemoryRecord(
            id=name, text=_ROWS[name], embedding=(1.0, 0.0), at=at, session_id="chat-a"
        )
        await store.add(record)
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(session_id=chat, turn_id="t1", query=query)
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text}, stamp=stamp)
    card = await tool.card(call)
    await tool.invoke(call)
    return card, sorted(hit.record.id for hit in await store.search((1.0, 0.0), k=10))


@pytest.mark.parametrize("chat", ["chat-a", "chat-new"])
@pytest.mark.parametrize(
    ("query", "text", "ids", "left"),
    [
        ("Forget my gym code.", "code", ("gym", "bike"), ["bike"]),
        ("Forget my gym code.", "code", ("bike", "gym"), ["bike"]),
        ("Forget my bike lock code.", "code", ("gym", "bike", "shed"), ["gym", "shed"]),
        ("Forget my gym code.", "code", ("gym", "bike", "shed"), ["bike", "shed"]),
        ("Vergiss meinen Bike Code.", "code", ("gym", "bike"), ["gym"]),
        ("Forget my other card.", "card", ("card", "card2"), []),
        ("Forget my gym code, keep the rest.", "code", ("gym", "bike"), ["bike"]),
        ("Forget my gym code, keep the rest.", "code", ("gym", "bike", "shed"), ["bike", "shed"]),
    ],
)
async def test_a_row_a_word_matches_and_no_word_of_the_message_names_is_kept(
    query: str, text: str, ids: tuple[str, ...], left: list[str], chat: str
) -> None:
    card, rows = await _forget(query, text, *ids, chat=chat)
    assert card is not None
    assert rows == left
    assert card.count(KEPT_LINE) == bool(left)
    assert "".join(card.split(KEPT_LINE)[1:]).count("\n- ") == len(left)


@pytest.mark.parametrize("chat", ["chat-a", "chat-new"])
@pytest.mark.parametrize(
    ("query", "ids"),
    [
        ("Forget my codes.", ("gym", "bike")),
        ("Forget the code.", ("gym", "bike")),
        ("Forget my gym code and my bike code.", ("gym", "bike")),
        ("Forget all my codes.", ("gym", "bike", "shed")),
        ("Forget the gym and the bike lock codes.", ("gym", "bike")),
        ("Forget my shed and bike codes.", ("bike", "shed")),
    ],
)
async def test_a_message_naming_each_row_or_none_lists_every_row_the_word_matches(
    query: str, ids: tuple[str, ...], chat: str
) -> None:
    card, rows = await _forget(query, "code", *ids, chat=chat)
    assert card is not None
    assert KEPT_LINE not in card
    assert rows == []


async def test_the_result_of_a_word_says_the_kept_rows_contain_the_text_not_the_value() -> None:
    store = InMemoryMemoryStore()
    for i, name in enumerate(("gym", "bike")):
        at = _AT + timedelta(minutes=i)
        await store.add(MemoryRecord(id=name, text=_ROWS[name], embedding=(1.0, 0.0), at=at))
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(turn_id="t1", query="Forget my gym code.")
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": "code"}, stamp=stamp)
    await tool.card(call)
    result = await tool.invoke(call)
    assert result.content == f"{forgot(1, 0, 1, 0, 'code')}."
    assert ("contain that text" in result.content, "value" in result.content) == (True, False)
    assert forgot(1, 1, 1, 0, "4242") == forgot(1, 1, 1)
