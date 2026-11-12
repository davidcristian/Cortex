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
from cortex_core.forget_inside import kept_rows
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 12, 2, 30, 0, tzinfo=UTC)
_CARD = "User: Remember that my card is 4111 1111 1111 4242.\nAssistant: Noted."
_GYM = "User: Remember that my gym code is 4242.\nAssistant: Noted."
_ALONE, _STORED, _BESIDE = "alone", "stored", "beside"
_ROWS = {_ALONE: (_CARD,), _STORED: (_CARD,), _BESIDE: (_CARD, _GYM)}
_CHAT = {_ALONE: "chat-new", _STORED: "chat-a", _BESIDE: "chat-new"}
_MESSAGES = (
    "Forget my gym code.",
    "Forget 4242.",
    "Forget the code 4242.",
    "Forget my Visa ending 4242.",
    "Forget the number ending 4242.",
    "Forget my card.",
    "Forget what I just told you.",
    "Forget that.",
    "Vergiss, was ich gerade gesagt habe.",
    "Oublie ce que je viens de dire.",
)
_LISTED = {
    _ALONE: ("", "r0", "r0", "r0", "r0", "r0", "", "r0", "", ""),
    _STORED: ("", "r0", "r0", "r0", "r0", "r0", "r0", "r0", "r0", "r0"),
    _BESIDE: ("r1", "r1", "r1", "", "", "r0", "", "", "", ""),
}
_CASES = [
    (scenario, message, listed)
    for scenario, column in _LISTED.items()
    for message, listed in zip(_MESSAGES, column, strict=True)
]


async def _deleted(scenario: str, query: str) -> list[str]:
    store = InMemoryMemoryStore()
    for index, row in enumerate(_ROWS[scenario]):
        at = _AT + timedelta(minutes=index)
        record = MemoryRecord(
            id=f"r{index}", text=row, embedding=(1.0, 0.0), at=at, session_id="chat-a"
        )
        await store.add(record)
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(session_id=_CHAT[scenario], turn_id="t1", query=query)
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": "4242"}, stamp=stamp)
    await tool.card(call)
    await tool.invoke(call)
    left = {hit.record.id for hit in await store.search((1.0, 0.0), k=10)}
    return sorted({f"r{index}" for index in range(len(_ROWS[scenario]))} - left)


@pytest.mark.parametrize(("scenario", "query", "listed"), _CASES)
async def test_a_last_group_forget_deletes_only_the_row_the_table_lists(
    scenario: str, query: str, listed: str
) -> None:
    assert await _deleted(scenario, query) == ([listed] if listed else [])


@pytest.mark.parametrize("query", ["Forget my Visa ending 4242.", "Forget my door code 4242."])
async def test_words_naming_neither_row_beside_the_code_keep_both_and_name_them(
    query: str,
) -> None:
    store = InMemoryMemoryStore()
    for index, row in enumerate(_ROWS[_BESIDE]):
        await store.add(MemoryRecord(id=f"r{index}", text=row, embedding=(1.0, 0.0), at=_AT))
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(session_id="chat-new", turn_id="t1", query=query)
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": "4242"}, stamp=stamp)
    assert await tool.card(call) is None
    result = await tool.invoke(call)
    assert result.kept == (" ".join(_GYM.split()),)
    assert result.inside == (" ".join(_CARD.split()),)


@pytest.mark.parametrize(
    ("query", "kept"),
    [
        ("Forget my Visa ending 4242.", ["gym"]),
        ("Forget my gym code 4242.", []),
        ("Forget the code 4242.", []),
        ("Forget my gym code.", []),
    ],
)
def test_kept_rows_keeps_a_whole_value_only_beside_a_kept_longer_one(
    query: str, kept: list[str]
) -> None:
    card = MemoryRecord(id="card", text=_CARD, embedding=(1.0, 0.0), at=_AT)
    gym = MemoryRecord(id="gym", text=_GYM, embedding=(1.0, 0.0), at=_AT)
    stamp = TurnStamp(session_id="chat-new", turn_id="t1", query=query)
    assert [row.id for row in kept_rows([gym], [card], "4242", stamp, ())] == kept
    assert kept_rows([gym], [], "4242", stamp, ()) == []


async def test_a_code_word_naming_no_row_keeps_the_gym_row_beside_the_newest_card() -> None:
    store = InMemoryMemoryStore()
    for index, row in enumerate((_GYM, _CARD)):
        at = _AT + timedelta(minutes=index)
        record = MemoryRecord(
            id=f"r{index}", text=row, embedding=(1.0, 0.0), at=at, session_id="chat-a"
        )
        await store.add(record)
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(session_id="chat-a", turn_id="t1", query="Forget my door code.")
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": "4242"}, stamp=stamp)
    assert await tool.card(call) is None
    result = await tool.invoke(call)
    assert result.kept == (" ".join(_GYM.split()),)
    assert result.inside == (" ".join(_CARD.split()),)
