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
from cortex_core.forget_unnamed import KEPT_LINE
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 13, 3, 30, 0, tzinfo=UTC)
_ROWS = {
    "card": "User: Remember that my card is 4111 1111 1111 4242.\nAssistant: Noted.",
    "card2": "User: Remember that my other card is 5500 0000 0000 4242.\nAssistant: Noted.",
    "karte": "User: Merke dir, meine Karte ist 4111 1111 1111 4242.\nAssistant: Notiert.",
    "mobile": "User: Remember that my mobile phone is 0721 555 4242.\nAssistant: Noted.",
    "middle": "User: Remember that my desk phone is 0721 4242 555.\nAssistant: Noted.",
    "gym": "User: Remember that my gym code is 4242.\nAssistant: Noted.",
    "reply": "User: Remember the garage.\nAssistant: Noted, the garage code is 4242.",
}


def _records(*ids: str) -> list[MemoryRecord]:
    return [
        MemoryRecord(
            id=name,
            text=_ROWS[name],
            embedding=(1.0, 0.0),
            at=_AT + timedelta(minutes=i),
            session_id="chat-a",
        )
        for i, name in enumerate(ids)
    ]


async def _card(query: str, *ids: str, chat: str) -> tuple[str | None, list[str]]:
    store = InMemoryMemoryStore()
    for record in _records(*ids):
        await store.add(record)
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(session_id=chat, turn_id="t1", query=query)
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": "4242"}, stamp=stamp)
    card = await tool.card(call)
    await tool.invoke(call)
    return card, sorted(hit.record.id for hit in await store.search((1.0, 0.0), k=10))


@pytest.mark.parametrize("chat", ["chat-a", "chat-new"])
@pytest.mark.parametrize(
    ("query", "ids", "left"),
    [
        ("Forget the card ending in 4242.", ("card", "mobile"), ["mobile"]),
        ("Forget the card ending in 4242.", ("mobile", "card"), ["mobile"]),
        ("Forget the card ending in 4242.", ("card", "middle"), ["middle"]),
        ("Forget my card ending in 4242.", ("karte", "mobile"), ["mobile"]),
        ("Oublie la carte qui finit par 4242.", ("card", "mobile"), ["mobile"]),
        ("Vergiss meine Karte mit der Endung 4242.", ("card", "mobile"), ["mobile"]),
        ("Forget my phone ending in 4242.", ("card", "mobile"), ["card"]),
        ("Forget the card ending in 4242.", ("card", "mobile", "gym"), ["gym", "mobile"]),
    ],
)
async def test_a_row_holding_the_value_only_in_a_longer_value_and_unnamed_is_kept(
    query: str, ids: tuple[str, ...], left: list[str], chat: str
) -> None:
    card, rows = await _card(query, *ids, chat=chat)
    assert card is not None
    assert rows == left
    assert card.split(KEPT_LINE)[1].count("\n- ") == len(left)


@pytest.mark.parametrize("chat", ["chat-a", "chat-new"])
@pytest.mark.parametrize(
    ("query", "ids"),
    [
        ("Forget 4242.", ("card", "mobile")),
        ("Forget everything ending in 4242.", ("card", "mobile")),
        ("Forget the card ending in 4242.", ("card", "card2")),
        ("Forget the card and the phone ending in 4242.", ("card", "mobile")),
        ("Forget my card and my mobile, both end in 4242.", ("card", "mobile")),
        ("Forget every 4242, the card first.", ("card", "mobile")),
        ("Forget the card ending in 4242.", ("card", "reply")),
    ],
)
async def test_a_row_the_message_names_or_a_message_naming_only_the_value_lists_it(
    query: str, ids: tuple[str, ...], chat: str
) -> None:
    card, rows = await _card(query, *ids, chat=chat)
    assert card is not None
    assert KEPT_LINE not in card
    assert rows == []


def test_only_a_named_row_this_call_matched_keeps_the_unnamed_group_holder() -> None:
    card, mobile = _records("card", "mobile")
    stamp = TurnStamp(session_id="chat-new", turn_id="t1", query="Forget the card ending in 4242.")
    assert kept_rows([mobile], [card], "4242", stamp, []) == [mobile]
    assert kept_rows([mobile], [], "4242", stamp, [card]) == []
