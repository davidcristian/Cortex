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
from cortex_core.forget_unnamed import asks_to_keep
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 9, 7, 0, 0, tzinfo=UTC)
_BIKE = "User: Remember that my bike lock code is 7319.\nAssistant: Noted."
_SHED = "User: Remember that the shed padlock code is also 7319.\nAssistant: Noted."
_GYM = "User: My gym locker is 7319.\nAssistant: Noted."


async def _numbers_left(text: str, query: str, *rows: str) -> tuple[bool | None, int]:
    store = InMemoryMemoryStore()
    for index, row in enumerate((_BIKE, _SHED, *rows)):
        at = _AT + timedelta(minutes=index)
        await store.add(MemoryRecord(id=f"r{index}", text=row, embedding=(1.0, 0.0), at=at))
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(session_id="chat-a", turn_id="t1", query=query)
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text}, stamp=stamp)
    assert await tool.card(call) is not None
    result = await tool.invoke(call)
    return result.numbers_left, result.forgot


@pytest.mark.parametrize(
    ("text", "query"),
    [
        ("7319", "Forget my bike lock code 7319, keep the shed one."),
        ("bike lock", "Forget my bike lock code, keep the shed one."),
        ("7319", "Forget my bike lock code 7319, keep everything else."),
        ("7319", "Forget my bike lock code 7319, keep the rest."),
        ("7319", "Forget my bike lock code 7319 but not the shed one."),
        ("7319", "Oublie le code du bike lock 7319, garde tout le reste."),
        ("7319", "Vergiss den bike lock Code 7319, behalte den shed Code."),
    ],
)
async def test_a_row_the_message_asked_to_keep_leaves_no_number_to_forget(
    text: str, query: str
) -> None:
    assert await _numbers_left(text, query) == (False, 1)


@pytest.mark.parametrize(
    ("text", "query", "rows"),
    [
        ("7319", "Forget my bike lock code 7319.", ()),
        ("bike lock", "Forget my bike lock code.", ()),
        ("7319", "Forget my bike lock code 7319, keep the shed one.", (_GYM,)),
        ("bike lock", "Forget my bike lock code, keep the shed one.", (_GYM,)),
        ("7319", "Forget my bike lock code 7319, don't keep the rest.", ()),
        ("7319", "Forget the rest stop and bike lock code 7319.", ()),
        ("7319", "Forget my bike lock code 7319, keep it.", ()),
    ],
)
async def test_a_row_the_message_did_not_ask_to_keep_still_leaves_the_number(
    text: str, query: str, rows: tuple[str, ...]
) -> None:
    assert await _numbers_left(text, query, *rows) == (True, 1)


@pytest.mark.parametrize(
    "query",
    [
        "Forget my bike lock code 7319, keep the shed one.",
        "Forget my bike lock code 7319, keep all the others.",
    ],
)
def test_a_keep_clause_names_a_row_by_its_words_or_by_keeping_the_rest(query: str) -> None:
    assert asks_to_keep(_SHED, query)


@pytest.mark.parametrize(
    "query",
    [
        "Forget my bike lock code 7319, keep the bike one.",
        "Forget the shed padlock code 7319.",
        "Forget all of 7319, but keep the bike one.",
        "",
    ],
)
def test_a_message_naming_the_row_only_to_forget_or_keeping_another_names_no_keep(
    query: str,
) -> None:
    assert not asks_to_keep(_SHED, query)
