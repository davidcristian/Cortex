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
from cortex_core.forget_kinds import names, read_kinds
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 13, 4, 30, 0, tzinfo=UTC)
_ROWS = {
    "telefon": "User: Merke dir, meine Telefonnummer ist 0721 555 019.\nAssistant: Notiert.",
    "carte": "User: Retiens que ma carte est 4111 1111 1111 4242.\nAssistant: Noté.",
    "card": "User: Remember that my card is 4111 1111 1111 4242.\nAssistant: Noted.",
    "gym": "User: Remember that my gym code is 4242.\nAssistant: Noted.",
}


async def _forget(query: str, text: str, *ids: str, chat: str) -> tuple[str | None, list[str]]:
    store = InMemoryMemoryStore()
    for i, name in enumerate(ids):
        at = _AT + timedelta(minutes=i)
        record = MemoryRecord(
            id=name, text=_ROWS[name], embedding=(1.0, 0.0), at=at, session_id="chat-a"
        )
        await store.add(record)
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(session_id=chat, turn_id="t1", query=query)
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text}, stamp=stamp)
    card = await tool.card(call)
    await tool.invoke(call)
    return card, sorted(hit.record.id for hit in await store.search((1.0, 0.0), k=10))


@pytest.mark.parametrize("chat", ["chat-a", "chat-new"])
@pytest.mark.parametrize(
    ("query", "text", "ids", "left"),
    [
        ("Forget my phone number, I don't need it anymore.", "0721 555 019", ("telefon",), []),
        ("Forget my card. I do not use it.", "4242", ("carte", "gym"), ["gym"]),
    ],
)
async def test_a_kind_word_lists_a_row_from_a_clause_holding_no_negation(
    query: str, text: str, ids: tuple[str, ...], left: list[str], chat: str
) -> None:
    card, rows = await _forget(query, text, *ids, chat=chat)
    assert card is not None
    assert rows == left


@pytest.mark.parametrize("chat", ["chat-a", "chat-new"])
@pytest.mark.parametrize(
    ("query", "text", "ids"),
    [
        ("Don't forget my phone number.", "0721 555 019", ("telefon",)),
        ("I don't need my phone number, forget it.", "0721 555 019", ("telefon",)),
        ("Vergiss nicht meine Karte.", "4242", ("carte", "gym")),
        ("Forget 4242, less the card.", "4242", ("carte", "gym")),
        ("Uită cardul 4242 mai puțin codul de la sală.", "4242", ("card", "gym")),
    ],
)
async def test_a_kind_word_in_a_clause_holding_a_negation_or_minus_lists_no_row(
    query: str, text: str, ids: tuple[str, ...], chat: str
) -> None:
    assert await _forget(query, text, *ids, chat=chat) == (None, sorted(ids))


def test_a_kind_word_lists_by_the_stem_of_a_compound_only_outside_a_negated_clause() -> None:
    kind = read_kinds("Vergiss meine Telefonnummer, nicht meine Karte.")
    assert ("telefon" in kind, "karte" in kind) == (True, False)
    assert (names({"karte"}, {"card"}, kind=kind), names({"karte"}, {"card"})) == (False, True)
