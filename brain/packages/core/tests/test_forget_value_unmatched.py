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
from cortex_core.forget_inside import INSIDE_ALL
from cortex_core.forget_longer import LONGER_ALL
from cortex_core.forget_results import NONE_FOUND
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 11, 4, 0, 0, tzinfo=UTC)
_ACCOUNT = "User: Remember that my phone account is 015 123 456 7890.\nAssistant: Noted."
_CARD = "User: My card is 4111111111114242.\nAssistant: Noted."
_ASKED = "Forget my phone account 015-123-456-7890."


async def _forget(text: str, query: str, row: str) -> tuple[str | None, str, bool, list[str]]:
    store = InMemoryMemoryStore()
    await store.add(MemoryRecord(id="row", text=row, embedding=(1.0, 0.0), at=_AT))
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(session_id="chat-a", turn_id="t1", query=query)
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text}, stamp=stamp)
    card = await tool.card(call)
    result = await tool.invoke(call)
    left = [hit.record.id for hit in await store.search((1.0, 0.0), k=10)]
    return card, result.content, result.matched_nothing, left


@pytest.mark.parametrize(
    ("text", "query"),
    [
        ("015-123-456-7890", _ASKED),
        ("015.123.456.7890", _ASKED),
        ("0151234567890", _ASKED),
        ("0151 2345 67890", "Forget my phone account 0151 2345 67890."),
    ],
)
async def test_a_value_in_other_separators_than_its_only_row_is_listed_and_deleted(
    text: str, query: str
) -> None:
    card, said, unmatched, left = await _forget(text, query, _ACCOUNT)
    assert card is not None
    assert card.splitlines() == [
        "Deletes for good, with no undo, these 1 remembered exchanges:",
        f"Listed because they also hold {text}:",
        "- User: Remember that my phone account is 015 123 456 7890. Assistant: Noted.",
    ]
    assert said.startswith("forgot 1 remembered exchanges;")
    assert (unmatched, left) == (False, [])


@pytest.mark.parametrize(
    ("text", "query", "row", "said"),
    [
        ("015-123-456-789", "Forget 015-123-456-789.", _ACCOUNT, NONE_FOUND),
        ("0151234567890", "Forget my phone 015 123 456 789.", _ACCOUNT, LONGER_ALL),
        ("4242", "Forget the card ending in 4242.", _CARD, INSIDE_ALL),
    ],
)
async def test_a_value_inside_a_longer_row_value_keeps_the_row_with_no_card(
    text: str, query: str, row: str, said: str
) -> None:
    card, content, unmatched, left = await _forget(text, query, row)
    assert card is None
    assert content == f"{said}."
    assert (unmatched, left) == (said == NONE_FOUND, ["row"])


@pytest.mark.parametrize(
    ("text", "row"),
    [
        ("1225", "User: The Christmas party is on 12/25.\nAssistant: Noted."),
        ("48-26", "User: Dentist appointment on 4/8/26.\nAssistant: Noted."),
        ("1030", "User: The meeting is at 10.30.\nAssistant: Noted."),
        ("1234", "User: We had 12 34 year olds.\nAssistant: Noted."),
    ],
)
async def test_a_code_against_a_date_a_time_or_small_numbers_lists_nothing(
    text: str, row: str
) -> None:
    card, said, matched_nothing, left = await _forget(text, f"Forget the code {text}.", row)
    assert (card, said.startswith(NONE_FOUND), matched_nothing, left) == (None, True, True, ["row"])


async def test_a_code_stored_in_groups_of_two_digits_is_listed_and_deleted() -> None:
    row = "User: My door code is 48 26.\nAssistant: Noted."
    card, _said, matched_nothing, left = await _forget("4826", "Forget the code 4826.", row)
    assert card is not None
    assert "Listed because they also hold 4826:" in card
    assert (matched_nothing, left) == (False, [])
