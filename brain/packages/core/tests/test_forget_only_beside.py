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
from cortex_core.forget_only import alone
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 26, 6, 0, 0, tzinfo=UTC)
_ROWS = {
    "locker": "User: Remember that my locker code is 4242.\nAssistant: Noted.",
    "phone": "User: Remember that my phone is 0721 555 4242.\nAssistant: Noted.",
    "card": "User: Remember that my card is 4111 1111 1111 4242.\nAssistant: Noted.",
}
_NAMED = frozenset({"card", "phone", "locker"})


async def _left(query: str, call_text: str = "4242") -> list[str]:
    store = InMemoryMemoryStore()
    for i, (name, text) in enumerate(_ROWS.items()):
        at = _AT + timedelta(minutes=i)
        await store.add(
            MemoryRecord(id=name, text=text, embedding=(1.0, 0.0), at=at, session_id="chat-a")
        )
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(session_id="chat-new", turn_id="t1", query=query)
    call = ToolCall(
        id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": call_text}, stamp=stamp
    )
    await tool.card(call)
    await tool.invoke(call)
    return sorted(hit.record.id for hit in await store.search((1.0, 0.0), k=10))


@pytest.mark.parametrize(
    "query",
    [
        "Forget all 4242, the card too, only the phone.",
        "Forget 4242, the card too, only the phone.",
        "Forget 4242, only the phone, the card too.",
        "Forget all 4242, also the card, just the phone.",
        "Forget all 4242, except the card, only the phone.",
        "Forget 4242, keep the card, only the phone.",
        "Forget 4242 except the phone, just the phone.",
        "Forget 4242 on the card and the locker, only the phone.",
    ],
)
async def test_a_word_for_only_keeps_each_row_its_run_does_not_name_beside_another_clause(
    query: str,
) -> None:
    left = await _left(query)
    assert {"card", "locker"} <= set(left)


@pytest.mark.parametrize(
    ("query", "left"),
    [
        ("Forget all 4242, only the card.", ["locker", "phone"]),
        ("Forget all 4242, just the card and the phone.", ["locker"]),
        ("Forget all 4242, the card too.", []),
        ("Forget the card 4242, the phone too.", ["locker"]),
        ("Forget all 4242, the card too, only the card.", ["locker", "phone"]),
    ],
)
async def test_a_word_for_only_or_an_adding_clause_alone_still_deletes_what_it_names(
    query: str, left: list[str]
) -> None:
    assert await _left(query) == left


@pytest.mark.parametrize("text", ["locker 4242", "code is 4242", "my locker code is 4242"])
@pytest.mark.parametrize(
    "query",
    [
        "Forget 4242, the card too, only the phone.",
        "Forget all 4242, only the card.",
        "Forget all 4242, except the card, just the phone.",
        "Forget 4242, keep the card, just the phone.",
        "Forget 4242, only the phone and the card.",
        "Forget 4242 just the phone.",
        "Forget all 4242 only the card.",
    ],
)
async def test_a_word_for_only_keeps_a_row_a_call_naming_it_beside_the_value_lists(
    query: str, text: str
) -> None:
    assert "locker" in await _left(query, text)


@pytest.mark.parametrize("text", ["locker 4242", "Remember that my locker code is 4242."])
@pytest.mark.parametrize(
    ("query", "left"),
    [
        ("Forget all 4242, only the locker.", ["card", "phone"]),
        ("Forget all 4242, just the locker.", ["card", "phone"]),
        ("Forget 4242 only the locker.", ["card", "phone"]),
        ("Forget 4242, the card too.", ["card", "phone"]),
    ],
)
async def test_a_call_naming_a_row_beside_the_value_deletes_it_when_the_run_names_it(
    query: str, left: list[str], text: str
) -> None:
    assert await _left(query, text) == left


@pytest.mark.parametrize(
    ("query", "words"),
    [
        ("Forget 4242, the card too, only the phone.", {"phone"}),
        ("Forget 4242, only the phone and the card.", {"card", "phone"}),
        ("Forget 4242, the card too.", set[str]()),
        ("Forget 4242, not only the phone.", set[str]()),
        ("Forget 4242, keep only the phone.", set[str]()),
        ("Forget 4242, only the phone too.", set[str]()),
        ("Forget 4242, only.", set[str]()),
        ("Forget 4242, on the phone.", set[str]()),
    ],
)
def test_alone_reads_the_rows_a_run_holding_a_word_for_only_limits_to(
    query: str, words: set[str]
) -> None:
    assert alone(query, "4242", _NAMED) == words
