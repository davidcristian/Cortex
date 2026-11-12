from datetime import UTC, datetime

import pytest

from cortex_core import (
    FORGET_CHOSEN_TOOL_NAME,
    GLOBAL_MEMORY_SCOPE,
    ForgetChosenTool,
    InMemoryMemoryStore,
    MemoryRecord,
    ToolCall,
)
from cortex_core.forget_inside import INSIDE_ALL, inside
from cortex_core.tools import ToolResult, TurnStamp

_AT = datetime(2026, 11, 12, 2, 0, 0, tzinfo=UTC)
_CARD = "User: Remember that my card is 4111 1111 1111 4242.\nAssistant: Noted."
_SHOWN = " ".join(_CARD.split())
_HEAD = "Deletes for good, with no undo, these 1 remembered exchanges:"


async def _forget(query: str, chat: str = "chat-new") -> tuple[str | None, ToolResult, list[str]]:
    store = InMemoryMemoryStore()
    record = MemoryRecord(id="r0", text=_CARD, embedding=(1.0, 0.0), at=_AT, session_id="chat-a")
    await store.add(record)
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(session_id=chat, turn_id="t1", query=query)
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": "4242"}, stamp=stamp)
    card = await tool.card(call)
    result = await tool.invoke(call)
    left = sorted(hit.record.id for hit in await store.search((1.0, 0.0), k=10))
    return card, result, left


@pytest.mark.parametrize(
    ("query", "chat"),
    [
        ("Forget my gym code.", "chat-new"),
        ("Oublie mon code de gym.", "chat-new"),
        ("Forget my Visa.", "chat-new"),
        ("Forget what I just told you.", "chat-new"),
        ("Forget my gym code.", "chat-a"),
    ],
)
async def test_a_card_alone_is_kept_when_the_message_lacks_the_text_and_names_another_word(
    query: str, chat: str
) -> None:
    card, result, left = await _forget(query, chat)
    assert card is None
    assert result.content == f"{INSIDE_ALL}."
    assert result.inside == (_SHOWN,)
    assert left == ["r0"]


@pytest.mark.parametrize(
    ("query", "chat"),
    [
        ("Forget the code 4242.", "chat-new"),
        ("Forget 4242.", "chat-new"),
        ("Forget the card ending in 4242.", "chat-new"),
        ("Forget my Visa ending 4242.", "chat-new"),
        ("Forget the number ending 4242.", "chat-new"),
        ("Forget my bank card.", "chat-new"),
        ("Oublie la carte qui finit par 4242.", "chat-new"),
        ("Vergiss meine Karte mit der Endung 4242.", "chat-new"),
        ("Forget my gym code 4242.", "chat-new"),
        ("Forget that.", "chat-new"),
        ("Vergiss das.", "chat-new"),
        ("Forget what I just told you.", "chat-a"),
    ],
)
async def test_a_card_alone_is_listed_when_the_message_holds_the_text_or_names_it(
    query: str, chat: str
) -> None:
    card, result, left = await _forget(query, chat)
    assert card == f"{_HEAD}\n- {_SHOWN}"
    assert result.inside == ()
    assert left == []


def test_a_last_group_row_is_kept_only_when_the_message_names_none_of_its_words() -> None:
    card = MemoryRecord(id="card", text=_CARD, embedding=(1.0, 0.0), at=_AT)
    locker = "User: Remember that my gym locker is 77 4242.\nAssistant: Noted."
    gym = MemoryRecord(id="gym", text=locker, embedding=(1.0, 0.0), at=_AT)
    phone = "User: Remember that my phone account is 015 123 456 4242.\nAssistant: Noted."
    account = MemoryRecord(id="account", text=phone, embedding=(1.0, 0.0), at=_AT)
    assert inside([card, gym], "4242", "Forget my gym code.") == {"card"}
    assert inside([account], "4242", "Forget my old phone.") == frozenset()
    assert inside([account], "4242", "Forget my gym code.") == {"account"}
    assert inside([card], "4242", "Forget my gym code.", (gym,)) == {"card"}
