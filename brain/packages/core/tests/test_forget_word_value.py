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
from cortex_core.forget_clauses import kept_again
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 21, 6, 0, 0, tzinfo=UTC)
_ROWS = {
    "locker": "User: Remember that my locker code is {value}.\nAssistant: Noted.",
    "card": "User: Remember that my card is 4111 1111 1111 {value}.\nAssistant: Noted.",
    "phone": "User: Remember that my phone is 0721 555 {value}.\nAssistant: Noted.",
}
_ALL = ["card", "locker", "phone"]
_NAMED = frozenset({"card", "locker", "phone"})


async def _forget(query: str, value: str) -> list[str]:
    store = InMemoryMemoryStore()
    for i, (name, text) in enumerate(_ROWS.items()):
        at = _AT + timedelta(minutes=i)
        record = MemoryRecord(
            id=name, text=text.format(value=value), embedding=(1.0, 0.0), at=at, session_id="chat-a"
        )
        await store.add(record)
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(session_id="chat-new", turn_id="t1", query=query)
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": value}, stamp=stamp)
    await tool.card(call)
    await tool.invoke(call)
    return sorted(hit.record.id for hit in await store.search((1.0, 0.0), k=10))


@pytest.mark.parametrize(
    ("query", "value"),
    [
        ("Forget the card card, the card stays.", "card"),
        ("Forget card on the card, the card stays.", "card"),
        ("Forget the card card. The card stays.", "card"),
        ("Forget card on the card. My card stays.", "card"),
        ("Forget the card tulip, the tulip stays.", "tulip"),
    ],
)
async def test_a_row_named_again_to_stay_is_kept_when_the_value_is_a_word_naming_it(
    query: str, value: str
) -> None:
    assert await _forget(query, value) == _ALL


@pytest.mark.parametrize(
    ("query", "value", "left"),
    [
        ("Forget the card card.", "card", []),
        ("Forget card.", "card", []),
        ("Forget card on the card.", "card", []),
        ("Forget the card card, the card one, thanks.", "card", []),
        ("Forget the card card, I don't need the card.", "card", []),
        ("Forget the card card, only the card.", "card", []),
        ("Forget the card card but the locker.", "card", ["locker"]),
        ("Forget tulip.", "tulip", []),
    ],
)
async def test_a_value_that_is_a_word_is_still_deleted_where_no_run_names_its_row_to_stay(
    query: str, value: str, left: list[str]
) -> None:
    assert await _forget(query, value) == left


@pytest.mark.parametrize(
    ("query", "value", "words"),
    [
        ("Forget the card card, the card stays.", "card", {"card"}),
        ("Forget card on the card, my card stays.", "card", {"card"}),
        ("Forget the card card but the locker.", "card", {"locker"}),
        ("Forget the card card, card stays.", "card", set[str]()),
        ("Forget tulip, I told you the tulip yesterday.", "tulip", set[str]()),
        ("Forget the card 4242, the card and the 4242 stay.", "4242", set[str]()),
        ("Forget the card 4242, the 4242 on the card stays.", "4242", {"card"}),
    ],
)
def test_kept_again_reads_a_word_value_after_a_word_for_the_as_a_row_name(
    query: str, value: str, words: set[str]
) -> None:
    assert kept_again(query, value, _NAMED) == words
