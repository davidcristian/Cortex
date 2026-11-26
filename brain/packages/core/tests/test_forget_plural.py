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
from cortex_core.forget_kinds import grows, prefixes
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 26, 3, 0, 0, tzinfo=UTC)
_ROWS = {
    "dulap": "User: Ține minte că codul de la dulap este 4242.\nAssistant: Notat.",
    "cardul": "User: Ține minte că cardul meu este 4111 1111 1111 4242.\nAssistant: Notat.",
    "telefonul": "User: Ține minte că telefonul meu este 0721 555 4242.\nAssistant: Notat.",
}
_ENGLISH = {
    "locker": "User: Remember that my locker code is 4242.\nAssistant: Noted.",
    "card": "User: Remember that my card is 4111 1111 1111 4242.\nAssistant: Noted.",
    "phone": "User: Remember that my phone is 0721 555 4242.\nAssistant: Noted.",
}
_TEXTS = ("cod", "card", "dulap", "telefon")


async def _deleted(query: str, text: str, rows: dict[str, str] = _ROWS) -> set[str]:
    store = InMemoryMemoryStore()
    for i, (name, row) in enumerate(rows.items()):
        at = _AT + timedelta(minutes=i)
        await store.add(
            MemoryRecord(id=name, text=row, embedding=(1.0, 0.0), at=at, session_id="a")
        )
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(session_id="chat-new", turn_id="t1", query=query)
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text}, stamp=stamp)
    await tool.card(call)
    await tool.invoke(call)
    return set(rows) - {hit.record.id for hit in await store.search((1.0, 0.0), k=10)}


@pytest.mark.parametrize("text", _TEXTS)
@pytest.mark.parametrize(
    ("plural", "single"),
    [
        ("Uită cardurile.", "Uită cardul."),
        ("Uită dulapurile.", "Uită dulapul."),
        ("Uită codurile.", "Uită codul."),
        ("Uită toate cardurile.", "Uită toate cardul."),
        ("Uită toate dulapurile.", "Uită toate dulapul."),
        ("Uită toate codurile.", "Uită toate codul."),
    ],
)
async def test_a_romanian_plural_row_word_deletes_what_the_singular_deletes(
    plural: str, single: str, text: str
) -> None:
    assert await _deleted(plural, text) == await _deleted(single, text)


@pytest.mark.parametrize(
    ("query", "text", "gone"),
    [
        ("Uită cardurile.", "telefon", set[str]()),
        ("Uită dulapurile.", "card", set[str]()),
        ("Uită codurile.", "telefon", set[str]()),
        ("Uită cardurile.", "card", {"cardul"}),
        ("Uită dulapurile.", "dulap", {"dulap"}),
    ],
)
async def test_a_romanian_plural_narrows_a_call_naming_another_row(
    query: str, text: str, gone: set[str]
) -> None:
    assert await _deleted(query, text) == gone


@pytest.mark.parametrize("text", ["card", "dulap", "cod"])
async def test_a_plural_that_changes_its_stem_names_no_row_and_the_call_decides(text: str) -> None:
    assert await _deleted("Uită telefoanele.", text) == await _deleted("Uită ceva.", text)


@pytest.mark.parametrize(
    ("word", "row"),
    [
        ("cardurile", {"cardul"}),
        ("codurile", {"codul"}),
        ("dulapurile", {"dulap"}),
        ("dulapuri", {"dulap"}),
    ],
)
def test_a_word_three_letters_longer_grows_from_a_row_word_it_starts_with(
    word: str, row: set[str]
) -> None:
    assert grows(word, row)


@pytest.mark.parametrize(
    ("word", "row"),
    [
        ("lockers", {"locker"}),
        ("remembered", {"remember"}),
        ("telefoanele", {"telefonul"}),
        ("cart", {"card"}),
        ("card", {"cardul"}),
        ("cartel", {"card"}),
        ("cartelul", {"card"}),
    ],
)
def test_a_word_shorter_by_its_growth_or_its_stem_grows_from_no_row_word(
    word: str, row: set[str]
) -> None:
    assert not grows(word, row)


def test_the_prefixes_of_a_word_run_from_four_letters_to_three_less_than_the_word() -> None:
    assert (prefixes("codurile"), prefixes("codul")) == (["codu", "codur"], [])


@pytest.mark.parametrize("query", ["Uită cardurile.", "Uită toate cardurile.", "Uită dulapurile."])
async def test_a_romanian_plural_beside_a_value_every_row_holds_keeps_every_row(query: str) -> None:
    assert await _deleted(query, "4242") == set()


async def test_a_longer_word_beside_a_word_naming_a_row_leaves_the_call_to_that_row() -> None:
    query = "Forget what you remembering about my card."
    assert await _deleted(query, "4242", _ENGLISH) == {"card"}
