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
from cortex_core.forget_kinds import kinds, names
from cortex_core.forget_unnamed import unnamed
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 13, 3, 0, 0, tzinfo=UTC)
_ROWS = {
    "card": "User: Remember that my card is 4111 1111 1111 4242.\nAssistant: Noted.",
    "gym": "User: Remember that my gym code is 4242.\nAssistant: Noted.",
    "phone": "User: Remember that my phone number is 0721 555 019.\nAssistant: Noted.",
    "karte": "User: Merke dir, meine Karte ist 4111 1111 1111 4242.\nAssistant: Notiert.",
    "mobile": "User: Remember that my mobile phone is 0721 555 4242.\nAssistant: Noted.",
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


async def _card(
    query: str, text: str, *ids: str, chat: str = "chat-new"
) -> tuple[str | None, list[str]]:
    store = InMemoryMemoryStore()
    for record in _records(*ids):
        await store.add(record)
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(session_id=chat, turn_id="t1", query=query)
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text}, stamp=stamp)
    card = await tool.card(call)
    await tool.invoke(call)
    return card, sorted(hit.record.id for hit in await store.search((1.0, 0.0), k=10))


@pytest.mark.parametrize(
    ("query", "text", "ids", "left"),
    [
        ("Vergiss meine Telefonnummer 0721 555 019.", "0721 555 019", ("phone",), []),
        ("Oublie ma carte.", "4111 1111 1111 4242", ("card",), []),
        ("Oublie la carte qui finit par 4242.", "4242", ("card", "gym"), ["gym"]),
        ("Oublie la carte qui finit par 4242.", "4242", ("gym", "card"), ["gym"]),
        ("Vergiss die Karte, die auf 4242 endet.", "4242", ("card", "gym"), ["gym"]),
        ("Forget my card ending in 4242.", "4242", ("karte", "gym"), ["gym"]),
    ],
)
async def test_a_kind_word_names_a_row_of_the_same_kind_in_another_language(
    query: str, text: str, ids: tuple[str, ...], left: list[str]
) -> None:
    card, rows = await _card(query, text, *ids)
    assert (card is not None, rows) == (True, left)


@pytest.mark.parametrize(
    "query",
    [
        "Vergiss meine Telefonnummer, die auf 4242 endet.",
        "Oublie mon téléphone 4242.",
        "Olvida mi teléfono 4242.",
    ],
)
@pytest.mark.parametrize("ids", [("card", "gym"), ("gym", "card")])
async def test_a_kind_word_of_another_kind_beside_the_same_value_keeps_every_row(
    query: str, ids: tuple[str, ...]
) -> None:
    assert await _card(query, "4242", *ids) == (None, ["card", "gym"])


def test_unnamed_lists_the_card_a_kind_word_names_and_keeps_the_code() -> None:
    kept = unnamed(_records("card", "gym"), "4242", "Oublie la carte qui finit par 4242.")
    assert [row.id for row in kept] == ["gym"]


async def test_a_message_naming_no_kind_word_still_keeps_every_row() -> None:
    card, rows = await _card("Oublie le vélo 4242.", "4242", "card", "gym")
    assert (card, rows) == (None, ["card", "gym"])


async def test_a_kind_word_in_a_keep_clause_keeps_the_row_of_that_kind() -> None:
    query = "Vergiss 0721 555 019, aber behalte das Telefon."
    card, rows = await _card(query, "0721 555 019", "phone")
    assert (card, rows) == (None, ["phone"])


def test_a_kind_is_read_only_from_the_closed_table() -> None:
    assert (kinds({"carte", "karte", "tarjeta", "cardul"}), kinds({"cartel", "map"})) == (
        {0},
        set(),
    )
    assert (names({"telefon"}, {"phone"}), names({"telefon"}, {"card"})) == (True, False)


@pytest.mark.parametrize(
    "query",
    [
        "N'oublie pas ma carte.",
        "Oublie le code 4242 moins celui de la carte.",
        "Olvida el código 4242 menos el de la tarjeta.",
        "Vergiss nicht die Karte, die auf 4242 endet.",
    ],
)
@pytest.mark.parametrize("ids", [("card", "gym"), ("gym", "card")])
async def test_a_kind_word_beside_a_negation_or_a_word_for_minus_lists_no_row(
    query: str, ids: tuple[str, ...]
) -> None:
    assert await _card(query, "4242", *ids) == (None, ["card", "gym"])


async def test_a_kind_word_keeps_the_newest_row_of_the_chat_it_does_not_name() -> None:
    card, rows = await _card("Oublie ma carte.", "4242", "card", "gym", "mobile", chat="chat-a")
    assert (card is not None, rows) == (True, ["gym", "mobile"])


async def test_a_negated_forget_keeps_a_row_only_a_kind_word_names() -> None:
    query = "Vergiss nicht meine Telefonnummer 0721 555 019."
    assert await _card(query, "0721 555 019", "phone") == (None, ["phone"])
