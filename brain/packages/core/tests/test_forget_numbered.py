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
from cortex_core.forget_kinds import extends
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 23, 9, 0, 0, tzinfo=UTC)
_ROWS = {
    "locker": "User: Remember that my locker code is 4242.\nAssistant: Noted.",
    "card": "User: Remember that my card is 4111 1111 1111 4242.\nAssistant: Noted.",
    "phone": "User: Remember that my phone is 0721 555 4242.\nAssistant: Noted.",
    "casier": "User: Retiens que le code du casier est 4242.\nAssistant: Noté.",
    "carte": "User: Retiens que ma carte est 4111 1111 1111 4242.\nAssistant: Noté.",
    "spind": "User: Merke dir, der Code vom Spind ist 4242.\nAssistant: Notiert.",
    "handy": "User: Merke dir, mein Handy ist 0721 555 4242.\nAssistant: Notiert.",
    "gimnasio": "User: Recuerda que el código del gimnasio es 4242.\nAssistant: Anotado.",
    "telefono": "User: Recuerda que mi teléfono es 0721 555 4242.\nAssistant: Anotado.",
}
_THREE = ("locker", "card", "phone")


async def _deleted(query: str, text: str, ids: tuple[str, ...] = _THREE) -> set[str]:
    store = InMemoryMemoryStore()
    for i, name in enumerate(ids):
        at = _AT + timedelta(minutes=i)
        row = MemoryRecord(id=name, text=_ROWS[name], embedding=(1.0, 0.0), at=at, session_id="a")
        await store.add(row)
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(session_id="chat-new", turn_id="t1", query=query)
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text}, stamp=stamp)
    await tool.card(call)
    await tool.invoke(call)
    left = {hit.record.id for hit in await store.search((1.0, 0.0), k=10)}
    return set(ids) - left


@pytest.mark.parametrize(
    ("query", "text", "gone"),
    [
        ("Forget everything and my code.", "phone", {"phone"}),
        ("Forget everything, my code too.", "card", {"card"}),
        ("Forget every code 4242.", "4242", {"locker"}),
        ("Forget my gym password.", "phone", {"phone"}),
        ("Forget my cardigan.", "card", {"card"}),
    ],
)
async def test_a_message_asking_for_every_row_or_naming_none_lists_what_the_call_names(
    query: str, text: str, gone: set[str]
) -> None:
    assert await _deleted(query, text) == gone


@pytest.mark.parametrize(
    "query",
    [
        "Forget every code.",
        "Forget all codes.",
        "Forget my codes.",
        "Forget all my codes.",
        "Forget every one of my codes.",
    ],
)
@pytest.mark.parametrize("text", ["phone", "my card is 4111", "card", "phone is 0721"])
async def test_a_code_word_in_another_number_or_after_a_word_for_all_keeps_other_rows(
    query: str, text: str
) -> None:
    assert await _deleted(query, text) == set()


@pytest.mark.parametrize(
    "query", ["Forget every code.", "Forget my codes.", "Forget all my codes.", "Forget my code."]
)
async def test_a_code_word_in_another_number_lists_the_row_holding_it(query: str) -> None:
    assert await _deleted(query, "locker code") == {"locker"}


@pytest.mark.parametrize(
    ("query", "text", "gone"),
    [
        ("Forget my cards.", "phone", set[str]()),
        ("Forget all my cards.", "phone", set[str]()),
        ("Forget my lockers.", "phone", set[str]()),
        ("Forget my cards.", "card", {"card"}),
        ("Forget my lockers.", "locker", {"locker"}),
        ("Forget my phones and the card.", "card", {"card"}),
    ],
)
async def test_a_row_word_in_another_number_names_the_row(
    query: str, text: str, gone: set[str]
) -> None:
    assert await _deleted(query, text) == gone


@pytest.mark.parametrize(
    ("query", "ids", "text"),
    [
        ("Oublie tous les codes.", ("casier", "carte"), "carte"),
        ("Oublie mes codes.", ("casier", "carte"), "carte"),
        ("Vergiss alle meine Codes.", ("spind", "handy"), "Handy"),
        ("Vergiss jeden Code.", ("spind", "handy"), "Handy"),
        ("Olvida mis códigos.", ("gimnasio", "telefono"), "teléfono"),
    ],
)
async def test_a_code_word_in_another_language_keeps_other_rows(
    query: str, ids: tuple[str, ...], text: str
) -> None:
    assert await _deleted(query, text, ids) == set()


@pytest.mark.parametrize(
    ("word", "row"),
    [("codes", {"code"}), ("boxes", {"box"}), ("códigos", {"código"}), ("cardio", {"card"})],
)
def test_a_word_one_or_two_letters_longer_extends_a_row_word(word: str, row: set[str]) -> None:
    assert extends(word, row)


@pytest.mark.parametrize(
    ("word", "row"),
    [("card", {"card"}), ("cardigan", {"card"}), ("pins", {"pi"}), ("code", {"codes"})],
)
def test_a_word_equal_shorter_or_much_longer_extends_no_row_word(word: str, row: set[str]) -> None:
    assert not extends(word, row)
