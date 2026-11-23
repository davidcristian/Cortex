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

_AT = datetime(2026, 11, 23, 6, 0, 0, tzinfo=UTC)
_ROWS = {
    "locker": "User: Remember that my locker code is 4242.\nAssistant: Noted.",
    "card": "User: Remember that my card is 4111 1111 1111 4242.\nAssistant: Noted.",
    "phone": "User: Remember that my phone is 0721 555 4242.\nAssistant: Noted.",
    "new": "User: Remember that my new card is 5500 0000 0000 4242.\nAssistant: Noted.",
    "casier": "User: Retiens que le code du casier est 4242.\nAssistant: Noté.",
    "carte": "User: Retiens que ma carte est 4111 1111 1111 4242.\nAssistant: Noté.",
    "telephone": "User: Retiens que mon téléphone est 0721 555 4242.\nAssistant: Noté.",
    "gimnasio": "User: Recuerda que el código del gimnasio es 4242.\nAssistant: Anotado.",
    "tarjeta": "User: Recuerda que mi tarjeta es 4111 1111 1111 4242.\nAssistant: Anotado.",
    "nueva": "User: Recuerda que mi tarjeta nueva es 5500 0000 0000 4242.\nAssistant: Anotado.",
    "telefono": "User: Recuerda que mi teléfono es 0721 555 4242.\nAssistant: Anotado.",
}
_ENGLISH = ("locker", "card", "phone")
_SHARED = ("card", "new", "locker")
_FRENCH = ("casier", "carte", "telephone")
_SPANISH = ("gimnasio", "tarjeta", "telefono")
_SPANISH_SHARED = ("tarjeta", "nueva", "gimnasio")


async def _left(query: str, ids: tuple[str, ...], text: str = "4242") -> list[str]:
    store = InMemoryMemoryStore()
    for i, name in enumerate(ids):
        at = _AT + timedelta(minutes=i)
        record = MemoryRecord(
            id=name, text=_ROWS[name], embedding=(1.0, 0.0), at=at, session_id="chat-a"
        )
        await store.add(record)
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(session_id="chat-new", turn_id="t1", query=query)
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text}, stamp=stamp)
    await tool.card(call)
    await tool.invoke(call)
    return sorted(hit.record.id for hit in await store.search((1.0, 0.0), k=10))


@pytest.mark.parametrize(
    ("query", "ids", "kept"),
    [
        ("Forget the card 4242, keep only the card.", _ENGLISH, "card"),
        ("Forget the card 4242, keep just the card.", _ENGLISH, "card"),
        ("Forget the card 4242, keep my old card.", _ENGLISH, "card"),
        ("Forget the card 4242, keep the card and my new card.", _SHARED, "card"),
        ("Forget the card 4242, keep my new card and the card.", _SHARED, "card"),
        (
            "Olvida la tarjeta 4242, guarda la tarjeta y mi tarjeta nueva.",
            _SPANISH_SHARED,
            "tarjeta",
        ),
        ("Forget all 4242 but the lockers.", _ENGLISH, "locker"),
        ("Forget all 4242, the lockers stays.", _ENGLISH, "locker"),
        ("Forget all 4242. The lockers stays.", _ENGLISH, "locker"),
        ("Oublie tous les 4242, le casiers reste.", _FRENCH, "casier"),
        ("Olvida todas las 4242, el teléfonos se queda.", _SPANISH, "telefono"),
    ],
)
async def test_a_row_any_reading_of_a_keep_clause_names_is_kept(
    query: str, ids: tuple[str, ...], kept: str
) -> None:
    assert kept in await _left(query, ids)
    assert kept in await _left(query, ids, kept if kept != "new" else "card")


@pytest.mark.parametrize(
    ("query", "ids", "left"),
    [
        ("Forget all 4242 but the lockers.", _ENGLISH, ["locker"]),
        ("Forget all 4242 but the locker.", _ENGLISH, ["locker"]),
        ("Forget all 4242 except the cards.", _ENGLISH, ["card"]),
        ("Forget all 4242 except the cardigans.", _ENGLISH, ["card", "locker", "phone"]),
        (
            "Olvida la tarjeta 4242, guarda el gimnasio, se queda.",
            _SPANISH,
            ["gimnasio", "telefono"],
        ),
        ("Forget the card 4242, keep the lockers.", _ENGLISH, ["locker", "phone"]),
        ("Olvida todas las 4242, el queda bien.", _SPANISH, []),
    ],
)
async def test_a_keep_clause_keeps_no_row_only_another_reading_names(
    query: str, ids: tuple[str, ...], left: list[str]
) -> None:
    assert await _left(query, ids) == left


@pytest.mark.parametrize(
    ("query", "ids", "text"),
    [
        ("Forget my old card 4242, keep the new card.", _SHARED, "4242"),
        ("Forget the card 4242, keep my new card.", _SHARED, "4242"),
        ("Olvida la tarjeta 4242, guarda la tarjeta nueva.", _SPANISH_SHARED, "4242"),
        ("Forget the card 4242, I don't need the card.", _ENGLISH, "4242"),
        ("Forget the card card, I don't need the card.", _ENGLISH, "card"),
    ],
)
async def test_a_keep_clause_naming_a_row_to_forget_beside_other_words_keeps_it(
    query: str, ids: tuple[str, ...], text: str
) -> None:
    assert await _left(query, ids, text) == sorted(ids)
