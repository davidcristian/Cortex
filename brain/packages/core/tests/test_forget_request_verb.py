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
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 26, tzinfo=UTC)
_ENGLISH = {
    "locker": "User: Remember that my locker code is 4242.\nAssistant: Noted.",
    "card": "User: Remember that my card is 4111 1111 1111 4242.\nAssistant: Noted.",
    "phone": "User: Remember that my phone is 0721 555 4242.\nAssistant: Noted.",
}
_SPANISH = {
    "gimnasio": "User: Recuerda que el código del gimnasio es 4242.\nAssistant: Anotado.",
    "tarjeta": "User: Recuerda que mi tarjeta es 4111 1111 1111 4242.\nAssistant: Anotado.",
    "telefono": "User: Recuerda que mi teléfono es 0721 555 4242.\nAssistant: Anotado.",
}
_ROMANIAN = {
    "dulap": "User: Ține minte că codul de la dulap este 4242.\nAssistant: Notat.",
    "cardul": "User: Ține minte că cardul meu este 4111 1111 1111 4242.\nAssistant: Notat.",
    "telefonul": "User: Ține minte că telefonul meu este 0721 555 4242.\nAssistant: Notat.",
}


async def _deleted(query: str, text: str, rows: dict[str, str]) -> set[str]:
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


@pytest.mark.parametrize("text", ["4242", "card"])
@pytest.mark.parametrize(
    "query",
    [
        "Forget what you remembered about my card.",
        "Forget what you remembers about my card.",
        "Forget what you remembering about my card.",
    ],
)
async def test_a_form_of_the_request_verb_beside_a_row_word_deletes_that_row_alone(
    query: str, text: str
) -> None:
    assert await _deleted(query, text, _ENGLISH) == {"card"}


@pytest.mark.parametrize(
    ("query", "text", "rows"),
    [
        ("Forget what you remembered about my locker.", "card", _ENGLISH),
        ("Olvida lo que recuerdas de mi teléfono.", "tarjeta", _SPANISH),
    ],
)
async def test_a_call_text_naming_another_row_than_the_row_word_deletes_no_row(
    query: str, text: str, rows: dict[str, str]
) -> None:
    assert await _deleted(query, text, rows) == set()


@pytest.mark.parametrize("text", ["dulap", "telefonul"])
@pytest.mark.parametrize(
    "query", ["Uită cardurile pe care le-ai mintea.", "Uită cardurile pe care le-ai minteaua."]
)
async def test_a_longer_form_of_the_request_verb_beside_a_plural_lists_no_other_row(
    query: str, text: str
) -> None:
    assert await _deleted(query, text, _ROMANIAN) == set()


async def test_a_form_of_the_request_verb_over_two_rows_deletes_the_row_word_s_row() -> None:
    rows = {name: _ENGLISH[name] for name in ("card", "phone")}
    assert await _deleted("Forget what you remembered about my card.", "4242", rows) == {"card"}


async def test_the_one_row_a_call_reaches_is_still_named_by_its_word_with_letters_added() -> None:
    rows = {name: _ENGLISH[name] for name in ("locker", "phone")}
    assert await _deleted("Forget my lockers 1234.", "locker", rows) == {"locker"}
