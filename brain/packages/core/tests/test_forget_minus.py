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

_AT = datetime(2026, 11, 13, 4, 30, 0, tzinfo=UTC)
_ROWS = {
    "card": "User: Remember that my card is 4111 1111 1111 4242.\nAssistant: Noted.",
    "card2": "User: Remember that my other card is 5500 0000 0000 4242.\nAssistant: Noted.",
    "carte": "User: Retiens que ma carte est 4111 1111 1111 4242.\nAssistant: Noté.",
    "karte": "User: Merke dir, meine Karte ist 4111 1111 1111 4242.\nAssistant: Notiert.",
    "gym": "User: Remember that my gym code is 4242.\nAssistant: Noted.",
}
_RO = "Uită codul 4242 mai puțin cel de pe card."


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


async def _forget(query: str, *ids: str, chat: str) -> tuple[str | None, list[str]]:
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
    ("query", "ids"),
    [
        (_RO, ("card", "gym")),
        (_RO, ("gym", "card")),
        (_RO, ("carte", "gym")),
        (_RO, ("karte", "gym")),
        ("Forget the code 4242 minus the one on the card.", ("card", "gym")),
        ("Forget the code 4242, less the card.", ("card", "gym")),
        ("Forget the card 4242, less the other card.", ("card", "card2")),
    ],
)
async def test_a_row_a_word_after_a_word_for_minus_names_is_kept_with_the_rest(
    query: str, ids: tuple[str, ...], chat: str
) -> None:
    card, rows = await _forget(query, *ids, chat=chat)
    assert card is None
    assert rows == sorted(ids)


@pytest.mark.parametrize("chat", ["chat-a", "chat-new"])
async def test_a_row_named_before_a_word_for_minus_is_listed_and_the_one_after_kept(
    chat: str,
) -> None:
    card, rows = await _forget("Forget my card 4242 minus the gym one.", "card", "gym", chat=chat)
    assert card is not None
    assert rows == ["gym"]
    assert card.split(KEPT_LINE)[1].count("\n- ") == 1


@pytest.mark.parametrize("chat", ["chat-a", "chat-new"])
@pytest.mark.parametrize(
    ("query", "left"),
    [
        ("Uită codul 4242 de pe card.", ["gym"]),
        ("Uită codul 4242.", ["card"]),
        ("Forget the code 4242 on the card.", ["gym"]),
        ("Forget the card 4242 and the gym code.", []),
    ],
)
async def test_a_forget_with_no_word_for_minus_keeps_its_listing(
    query: str, left: list[str], chat: str
) -> None:
    card, rows = await _forget(query, "card", "gym", chat=chat)
    assert card is not None
    assert rows == left


def test_a_word_for_minus_alone_or_last_names_no_row_to_keep() -> None:
    card, gym = _records("card", "gym")
    stamp = TurnStamp(session_id="chat-a", turn_id="t1", query="Forget the card 4242, minus.")
    assert kept_rows([card, gym], [], "4242", stamp, []) == [gym]
