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
from cortex_core.forget_longer import LONGER_ALL, LONGER_LINE, beside, longer
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 11, 3, 0, 0, tzinfo=UTC)
_ACCOUNT = "User: Remember that my phone account is 015 123 456 7890.\nAssistant: Noted."
_SHOWN = "- User: Remember that my phone account is 015 123 456 7890. Assistant: Noted."
_BOTH = "User: My phone is 015 123 456 789 and the account 015 123 456 7890.\nAssistant: Noted."
_CARD = "User: Remember my card number 4242 4242 4242 4242.\nAssistant: Noted."
_BANK = "User: Remember that my bank account is 44170 and my PIN is 44 17.\nAssistant: Noted."
_LONGER = "015 123 456 7890"


def _record(record_id: str, text: str, minutes: int = 0) -> MemoryRecord:
    return MemoryRecord(
        id=record_id, text=text, embedding=(1.0, 0.0), at=_AT + timedelta(minutes=minutes)
    )


async def _forget(
    text: str, query: str, *rows: MemoryRecord
) -> tuple[list[str] | None, str, list[str]]:
    store = InMemoryMemoryStore()
    for row in rows:
        await store.add(row)
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(session_id="chat-a", turn_id="t1", query=query)
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text}, stamp=stamp)
    card = await tool.card(call)
    result = await tool.invoke(call)
    left = sorted(hit.record.id for hit in await store.search((1.0, 0.0), k=100))
    return (None if card is None else card.splitlines()), result.content, left


@pytest.mark.parametrize(
    "query",
    [
        "Forget the card ending in 4242.",
        "Forget my card 4242.",
        "Forget the card number 4242 4242 4242 4242.",
    ],
)
async def test_a_card_named_by_its_end_is_deleted(query: str) -> None:
    lines, _, left = await _forget("4242 4242 4242 4242", query, _record("card", _CARD))
    assert lines is not None
    assert lines[0] == "Deletes for good, with no undo, these 1 remembered exchanges:"
    assert left == []


@pytest.mark.parametrize("text", ["4417", "44 17"])
async def test_a_row_holding_the_pin_and_a_longer_account_is_deleted(text: str) -> None:
    lines, _, left = await _forget(text, "Forget my PIN 4417.", _record("bank", _BANK))
    assert lines is not None
    assert lines[0] == "Deletes for good, with no undo, these 1 remembered exchanges:"
    assert left == []


@pytest.mark.parametrize(
    "query",
    [
        "Forget my phone 015 123 456 789.",
        "Forget my phone account 015 123 456 789.",
        "Forget the phone number 015 123 456 789.",
    ],
)
async def test_a_call_naming_a_longer_number_than_the_message_keeps_its_row(query: str) -> None:
    lines, said, left = await _forget(_LONGER, query, _record("account", _ACCOUNT))
    assert (lines, said, left) == (None, f"{LONGER_ALL}.", ["account"])


@pytest.mark.parametrize(
    "query",
    [
        "Forget my phone account 015 123 456 7890.",
        "Forget my phone account 0151234567890.",
        "Forget my phone account.",
        "Forget my phone 0170 999 888.",
    ],
    ids=["names-it", "names-it-joined", "names-no-value", "names-another-value"],
)
async def test_a_message_not_naming_a_shorter_value_still_lists_the_row(query: str) -> None:
    lines, _, left = await _forget(_LONGER, query, _record("account", _ACCOUNT))
    assert lines is not None
    assert lines[1] == _SHOWN
    assert left == []


async def test_a_row_holding_the_message_value_on_its_own_is_listed_beside_a_kept_row() -> None:
    query = "Forget my phone 015 123 456 789."
    rows = _record("both", _BOTH), _record("account", _ACCOUNT, 1)
    lines, said, left = await _forget(_LONGER, query, *rows)
    assert lines == [
        "Deletes for good, with no undo, these 1 remembered exchanges:",
        "- User: My phone is 015 123 456 789 and the account 015 123 456 7890. Assistant: Noted.",
        LONGER_LINE,
        _SHOWN,
    ]
    assert said == f"{beside(1, 1)}."
    assert left == ["account"]


def test_every_value_the_message_names_must_sit_inside_a_longer_one() -> None:
    row = _record("account", _ACCOUNT)
    assert longer([row], _LONGER, "Forget 015 123 456 789 and 0170 5555.") == []
    assert longer([row], _LONGER, "Forget 015 123 456 789 and 123 456 7.") == [row]
    assert longer([row], "phone", "Forget my phone 015 123 456 789.") == []
