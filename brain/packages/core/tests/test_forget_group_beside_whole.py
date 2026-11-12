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
from cortex_core.forget_inside import INSIDE_LINE, forgot_within, inside
from cortex_core.forget_unnamed import KEPT_LINE
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 12, 1, 0, 0, tzinfo=UTC)
_CARD = "User: Remember that my card is 4111 1111 1111 4242.\nAssistant: Noted."
_VISA = "User: Remember that my Visa is 4111 1111 1111 4242.\nAssistant: Noted."
_GYM = "User: Remember that my gym code is 4242.\nAssistant: Noted."
_HEAD = "Deletes for good, with no undo, these 1 remembered exchanges:"


def _line(row: str) -> str:
    return "- " + " ".join(row.split())


async def _forget(
    query: str, *rows: str, chat: str = "chat-new"
) -> tuple[list[str], str, list[str]]:
    store = InMemoryMemoryStore()
    for index, row in enumerate(rows):
        at = _AT + timedelta(minutes=index)
        record = MemoryRecord(
            id=f"r{index}", text=row, embedding=(1.0, 0.0), at=at, session_id="chat-a"
        )
        await store.add(record)
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(session_id=chat, turn_id="t1", query=query)
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": "4242"}, stamp=stamp)
    card = await tool.card(call)
    assert card is not None
    result = await tool.invoke(call)
    left = sorted(hit.record.id for hit in await store.search((1.0, 0.0), k=10))
    return card.splitlines(), result.content, left


@pytest.mark.parametrize(
    ("query", "chat"),
    [
        ("Forget my gym code.", "chat-new"),
        ("Forget the code 4242.", "chat-new"),
        ("Forget 4242.", "chat-new"),
        ("Forget what I just told you.", "chat-a"),
        ("Forget the gym code I asked you to remember.", "chat-new"),
    ],
)
async def test_a_last_group_row_is_kept_when_another_row_holds_the_code_whole(
    query: str, chat: str
) -> None:
    card, said, left = await _forget(query, _CARD, _GYM, chat=chat)
    assert card == [_HEAD, _line(_GYM), INSIDE_LINE, _line(_CARD)]
    assert said == f"{forgot_within(1, 1)}."
    assert left == ["r0"]


async def test_a_message_naming_the_card_lists_it_and_keeps_the_gym_code() -> None:
    card, _, left = await _forget("Forget the card ending in 4242.", _CARD, _GYM)
    assert card == [_HEAD, _line(_CARD), KEPT_LINE, _line(_GYM)]
    assert left == ["r1"]


async def test_a_word_only_the_longer_value_row_has_lists_that_row() -> None:
    card, _, left = await _forget("Forget my Visa 4242.", _VISA, _GYM)
    assert card == [_HEAD, _line(_VISA), KEPT_LINE, _line(_GYM)]
    assert left == ["r1"]


def test_inside_keeps_a_last_group_only_beside_a_row_holding_the_text_whole() -> None:
    card = MemoryRecord(id="card", text=_CARD, embedding=(1.0, 0.0), at=_AT)
    gym = MemoryRecord(id="gym", text=_GYM, embedding=(1.0, 0.0), at=_AT)
    assert inside([card], "4242", "Forget 4242.") == frozenset()
    assert inside([card, gym], "4242", "Forget 4242.") == {"card"}
    assert inside([card], "4242", "Forget 4242.", (gym,)) == {"card"}
    assert inside([card], "4242", "", (gym,)) == frozenset()


async def test_what_was_just_said_lists_the_card_when_the_chat_stored_it_last() -> None:
    card, _, left = await _forget("Forget what I just told you.", _GYM, _CARD, chat="chat-a")
    assert card == [_HEAD, _line(_CARD), KEPT_LINE, _line(_GYM)]
    assert left == ["r0"]


async def test_a_message_naming_the_gym_keeps_the_card_the_chat_stored_last() -> None:
    card, _, left = await _forget("Forget my gym code.", _GYM, _CARD, chat="chat-a")
    assert card == [_HEAD, _line(_GYM), INSIDE_LINE, _line(_CARD)]
    assert left == ["r1"]
