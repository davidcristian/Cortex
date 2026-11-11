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
from cortex_core.forget_inside import INSIDE_ALL, INSIDE_LINE, inside
from cortex_core.tools import ToolResult, TurnStamp

_AT = datetime(2026, 11, 11, 6, 0, 0, tzinfo=UTC)
_IBAN = "User: My IBAN is RO49 AAAA 1B31 0075 9384 0000.\nAssistant: Noted."
_CARD = "User: My card is 4111 1111 1111 4242.\nAssistant: Noted."
_DOOR = "User: The door code is 0075.\nAssistant: Noted."
_IBAN_LINE = "- User: My IBAN is RO49 AAAA 1B31 0075 9384 0000. Assistant: Noted."
_DOOR_LINE = "- User: The door code is 0075. Assistant: Noted."


async def _forget(
    text: str, query: str, *rows: str
) -> tuple[list[str] | None, ToolResult, list[str]]:
    store = InMemoryMemoryStore()
    for index, row in enumerate(rows):
        record = MemoryRecord(
            id=f"r{index}", text=row, embedding=(1.0, 0.0), at=_AT + timedelta(minutes=index)
        )
        await store.add(record)
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(session_id="chat-a", turn_id="t1", query=query)
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text}, stamp=stamp)
    card = await tool.card(call)
    result = await tool.invoke(call)
    left = sorted(hit.record.id for hit in await store.search((1.0, 0.0), k=10))
    return (None if card is None else card.splitlines()), result, left


@pytest.mark.parametrize(
    ("text", "query", "row"),
    [
        ("0075", "Forget the code 0075.", _IBAN),
        ("0075", "Forget 0075.", _IBAN),
        ("1111 4242", "Forget the code 1111 4242.", _CARD),
        ("1B31 0075", "Forget the code 1B31 0075.", _IBAN),
    ],
)
async def test_a_code_held_only_as_a_group_of_a_longer_value_keeps_the_row_with_no_card(
    text: str, query: str, row: str
) -> None:
    card, result, left = await _forget(text, query, row)
    assert card is None
    assert result.content == f"{INSIDE_ALL}."
    assert result.inside is not None
    assert len(result.inside) == 1
    assert left == ["r0"]


@pytest.mark.parametrize(
    ("text", "query", "row"),
    [
        ("4242", "Forget the card ending in 4242.", _CARD),
        ("4242", "Forget the code 4242.", _CARD),
        ("1111 4242", "Forget my card 1111 4242.", _CARD),
        ("0075", "Forget the code 0075 from my IBAN.", _IBAN),
        ("0075", "Forget my bank account, it has 0075 in it.", _IBAN),
        ("0075", "Forget RO49 AAAA 1B31 0075 9384 0000.", _IBAN),
        ("0075", "Forget the code 0075.", _DOOR),
        ("0075", "Forget the code 0075.", "User: Door 0075, IBAN RO49 AAAA 1B31 0075 9384 0000."),
        ("4111 1111 1111 4242", "Forget 4111 1111 1111 4242.", _CARD),
    ],
)
async def test_a_kind_named_a_last_group_or_a_code_alone_still_lists_and_deletes_the_row(
    text: str, query: str, row: str
) -> None:
    card, result, left = await _forget(text, query, row)
    assert card is not None
    assert card[0] == "Deletes for good, with no undo, these 1 remembered exchanges:"
    assert INSIDE_LINE not in card
    assert result.content.startswith("forgot 1 remembered exchanges")
    assert left == []


async def test_a_code_alone_is_listed_and_the_row_holding_it_as_a_group_is_shown_kept() -> None:
    card, result, left = await _forget("0075", "Forget the code 0075.", _IBAN, _DOOR)
    assert card == [
        "Deletes for good, with no undo, these 1 remembered exchanges:",
        _DOOR_LINE,
        INSIDE_LINE,
        _IBAN_LINE,
    ]
    assert result.content.startswith("forgot 1 remembered exchanges; 1 other remembered")
    assert left == ["r0"]


async def test_a_row_also_holding_the_code_in_other_separators_is_listed_once() -> None:
    row = "User: My IBAN is RO49 AAAA 1B31 0075 9384 0000 and the door code is 00 75."
    card, result, left = await _forget("0075", "Forget the code 0075.", row)
    assert card is not None
    assert card[:2] == [
        "Deletes for good, with no undo, these 1 remembered exchanges:",
        "Listed because they also hold 0075:",
    ]
    assert INSIDE_LINE not in card
    assert len(card) == 3
    assert (result.inside, left) == ((), [])


def test_inside_keeps_a_group_only_when_given_the_message() -> None:
    rows = [MemoryRecord(id="iban", text=_IBAN, embedding=(1.0, 0.0), at=_AT)]
    assert inside(rows, "0075") == frozenset()
    assert inside(rows, "0075", "Forget 0075.") == frozenset({"iban"})
    assert inside(rows, "0075", "Forget the IBANs.") == frozenset()
