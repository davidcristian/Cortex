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
from cortex_core.forget_unnamed import KEPT_LINE, unnamed
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 13, 3, 0, 0, tzinfo=UTC)
_ROWS = {
    "card": "User: Remember that my card is 4111 1111 1111 4242.\nAssistant: Noted.",
    "gym": "User: Remember that my gym code is 4242.\nAssistant: Noted.",
    "door": "User: Remember that my door code is 4242 too.\nAssistant: Noted.",
    "fee": "User: Remember that the gym fee was 4242 €.\nAssistant: Noted.",
    "later": "User: What is my locker code?\nAssistant: Your locker code is 4242.",
}
_ALL = ["card", "gym", "door"]


def _records(*ids: str) -> list[MemoryRecord]:
    return [
        MemoryRecord(id=name, text=_ROWS[name], embedding=(1.0, 0.0), at=_AT + timedelta(minutes=i))
        for i, name in enumerate(ids)
    ]


def _kept(query: str, *ids: str) -> list[str]:
    return [row.id for row in unnamed(_records(*ids), "4242", query)]


@pytest.mark.parametrize(
    "query",
    [
        "Forget every 4242 except the card.",
        "Forget every 4242 but keep the card.",
        "Forget 4242, keep my card.",
        "Oublie tous les 4242 sauf la carte.",
    ],
)
async def test_a_value_alone_beside_a_clause_naming_the_card_lists_the_row_holding_it_whole(
    query: str,
) -> None:
    store = InMemoryMemoryStore()
    for record in _records("card", "gym"):
        await store.add(record)
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(turn_id="t1", query=query)
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": "4242"}, stamp=stamp)
    card = await tool.card(call)
    assert card is not None
    lines = card.splitlines()
    assert (len(lines), "gym code" in lines[1], lines[2], "my card" in lines[3]) == (
        4,
        True,
        KEPT_LINE,
        True,
    )
    await tool.invoke(call)
    assert [hit.record.id for hit in await store.search((1.0, 0.0), k=10)] == ["card"]


@pytest.mark.parametrize(
    ("query", "ids", "kept"),
    [
        ("Forget 4242 except my gym code.", ("card", "gym"), ["card", "gym"]),
        ("Forget every 4242 except the card.", ("card", "gym", "door"), ["card"]),
        ("Forget 4242 but keep the gym and door codes.", ("card", "gym", "door"), _ALL),
        ("Forget 4242 except the gym one.", ("card", "gym", "door"), ["card", "gym"]),
    ],
)
def test_a_value_alone_lists_the_rows_holding_it_whole_that_the_clause_does_not_name(
    query: str, ids: tuple[str, ...], kept: list[str]
) -> None:
    assert _kept(query, *ids) == kept


@pytest.mark.parametrize(
    "query",
    [
        "Forget every 4242 except the phone.",
        "Forget every 4242 except the card and the boat.",
        "Forget 4242 but keep the code.",
        "Forget every 4242 but keep it quiet.",
        "Vergiss 4242, aber behalte die vom Schuppen.",
    ],
)
def test_a_keep_clause_with_a_word_naming_no_row_beside_a_value_alone_keeps_every_row(
    query: str,
) -> None:
    assert _kept(query, "card", "gym") == ["card", "gym"]


def test_a_value_beside_a_word_naming_no_row_lists_no_row_by_value() -> None:
    assert _kept("Forget my locker 4242 except the card.", "card", "gym") == ["card", "gym"]


def test_a_value_alone_lists_no_row_holding_it_as_an_amount_or_only_in_its_reply() -> None:
    query = "Forget every 4242 except the card."
    assert _kept(query, "card", "fee", "later") == ["card", "fee", "later"]
