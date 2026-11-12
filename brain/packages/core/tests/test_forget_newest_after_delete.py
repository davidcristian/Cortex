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
from cortex_core.forget_unnamed import just_said
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 12, 6, 0, 0, tzinfo=UTC)
_JUST = "Forget what I just told you."
_ROWS = {
    "card": "User: Remember that my card is 4111 1111 1111 4242.\nAssistant: Noted.",
    "gym": "User: Remember that my gym code is 4242.\nAssistant: Noted.",
    "locker": "User: Remember that my locker code is 4242.\nAssistant: Noted.",
    "dog": "User: Remember that my dog is called Rex.\nAssistant: Noted.",
}


def _row(name: str, chat: str | None, minute: int) -> MemoryRecord:
    at = _AT + timedelta(minutes=minute)
    return MemoryRecord(id=name, text=_ROWS[name], embedding=(1.0, 0.0), at=at, session_id=chat)


async def _forget(query: str, texts: tuple[str, ...], *rows: tuple[str, str]) -> list[str]:
    store = InMemoryMemoryStore()
    for minute, (name, chat) in enumerate(rows):
        await store.add(_row(name, chat, minute))
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(session_id="chat-a", turn_id="t1", query=query)
    for index, text in enumerate(texts):
        call = ToolCall(
            id=f"c{index}", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text}, stamp=stamp
        )
        await tool.card(call)
        await tool.invoke(call)
    return sorted(hit.record.id for hit in await store.search((1.0, 0.0), k=10))


async def test_a_later_call_deletes_the_card_stored_after_the_deleted_gym_code() -> None:
    rows = (("gym", "chat-a"), ("card", "chat-a"))
    assert await _forget(_JUST, ("gym code", "4242"), *rows) == []


async def test_a_later_call_keeps_the_card_stored_before_the_deleted_gym_code() -> None:
    rows = (("card", "chat-a"), ("gym", "chat-a"))
    assert await _forget(_JUST, ("gym code", "4242"), *rows) == ["card"]


@pytest.mark.parametrize("minute", [0, 1])
async def test_a_deleted_row_of_another_chat_leaves_the_newest_row_listed(minute: int) -> None:
    rows = [("card", "chat-a"), ("gym", "chat-b")]
    ordered = rows if minute else rows[::-1]
    assert await _forget(_JUST, ("gym code", "4242"), *ordered) == []


async def test_a_later_call_deletes_the_card_after_the_dog_of_another_chat() -> None:
    query = "Forget my dog and the 4242 I just told you."
    rows = (("card", "chat-a"), ("dog", "chat-b"))
    assert await _forget(query, ("dog", "4242"), *rows) == []


@pytest.mark.parametrize(
    ("order", "left"), [(("gym", "locker"), []), (("locker", "gym"), ["locker"])]
)
async def test_a_later_call_reads_the_newest_whole_code_against_the_deleted_one(
    order: tuple[str, str], left: list[str]
) -> None:
    rows = tuple((name, "chat-a") for name in order)
    assert await _forget(_JUST, ("gym", "4242"), *rows) == left


def test_just_said_reads_a_deleted_row_of_the_chat_newer_than_the_newest_row() -> None:
    card = _row("card", "chat-a", 1)
    assert just_said([card], "chat-a", [_row("gym", "chat-a", 2)]) is None
    assert just_said([card], "chat-a", [_row("gym", "chat-a", 1)]) == "card"
    assert just_said([card], "chat-a", [_row("gym", "chat-a", 0)]) == "card"
    assert just_said([card], "chat-a", [_row("gym", "chat-b", 2)]) == "card"
    assert just_said([card], None, [_row("gym", None, 2)]) is None


@pytest.mark.parametrize(
    "query", ["Forget my gym locker.", "Forget everything about my gym, 4242."]
)
@pytest.mark.parametrize("first", ["gym code", "4242"])
async def test_a_later_call_keeps_the_card_when_the_message_names_the_deleted_gym_code(
    query: str, first: str
) -> None:
    rows = (("gym", "chat-a"), ("card", "chat-a"))
    assert await _forget(query, (first, "4242"), *rows) == ["card"]
