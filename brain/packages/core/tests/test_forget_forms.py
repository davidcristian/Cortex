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
from cortex_core.forget_forms import FORMS, LANGUAGES, UNREAD, words
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 15, 6, 0, 0, tzinfo=UTC)
_ROWS = {
    "locker": "User: Remember that my locker code is 4242.\nAssistant: Noted.",
    "phone": "User: Remember that my phone is 0721 555 4242.\nAssistant: Noted.",
    "card": "User: Remember that my card is 4111 1111 1111 4242.\nAssistant: Noted.",
    "todo": "User: Remember that my todo list code is 4242.\nAssistant: Noted.",
    "casier": "User: Retiens que le code du casier est 4242.\nAssistant: Noté.",
    "carte": "User: Retiens que ma carte est 4111 1111 1111 4242.\nAssistant: Noté.",
    "telephone": "User: Retiens que mon téléphone est 0721 555 4242.\nAssistant: Noté.",
    "spind": "User: Merke dir, der Code vom Spind ist 4242.\nAssistant: Notiert.",
    "karte": "User: Merke dir, meine Karte ist 4111 1111 1111 4242.\nAssistant: Notiert.",
    "handy": "User: Merke dir, mein Handy ist 0721 555 4242.\nAssistant: Notiert.",
    "gimnasio": "User: Recuerda que el código del gimnasio es 4242.\nAssistant: Anotado.",
    "tarjeta": "User: Recuerda que mi tarjeta es 4111 1111 1111 4242.\nAssistant: Anotado.",
    "telefono": "User: Recuerda que mi teléfono es 0721 555 4242.\nAssistant: Anotado.",
    "dulap": "User: Ține minte că codul de la dulap este 4242.\nAssistant: Notat.",
    "cardul": "User: Ține minte că cardul meu este 4111 1111 1111 4242.\nAssistant: Notat.",
    "telefonul": "User: Ține minte că telefonul meu este 0721 555 4242.\nAssistant: Notat.",
}
_ENGLISH = ("locker", "card", "phone")
_FRENCH = ("casier", "carte", "telephone")
_GERMAN = ("spind", "karte", "handy")
_SPANISH = ("gimnasio", "tarjeta", "telefono")
_ROMANIAN = ("dulap", "cardul", "telefonul")


async def _gone(query: str, ids: tuple[str, ...], text: str = "4242") -> list[str]:
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
    left = {hit.record.id for hit in await store.search((1.0, 0.0), k=10)}
    return sorted(set(ids) - left)


def test_each_cell_holds_a_word_or_has_a_written_reason() -> None:
    unexplained = [
        (form, language)
        for form, cells in FORMS.items()
        for language, cell in zip(LANGUAGES, cells, strict=True)
        if not cell.split() and not UNREAD.get((form, language), "").strip()
    ]
    assert unexplained == []


def test_each_reason_is_for_a_cell_of_another_language_than_english() -> None:
    assert all(form in FORMS and language in LANGUAGES[1:] for form, language in UNREAD)


def test_the_words_of_a_row_are_those_of_its_five_cells() -> None:
    assert words("except") == {
        "except",
        "excluding",
        "sauf",
        "hormis",
        "excepté",
        "außer",
        "ausgenommen",
        "excepto",
        "salvo",
        "exceptând",
    }


@pytest.mark.parametrize(
    ("query", "ids", "gone"),
    [
        ("Forget all 4242.", _ENGLISH, ["card", "locker", "phone"]),
        ("Oublie toute 4242.", _FRENCH, ["carte", "casier", "telephone"]),
        ("Oublie toute 4242 sauf la carte.", _FRENCH, ["casier", "telephone"]),
        ("Vergiss jede 4242.", _GERMAN, ["handy", "karte", "spind"]),
        ("Vergiss jedes 4242.", _GERMAN, ["handy", "karte", "spind"]),
        ("Vergiss jeden Code 4242, die Karte auch.", _GERMAN, ["karte", "spind"]),
        ("Olvida todas las 4242.", _SPANISH, ["gimnasio", "tarjeta", "telefono"]),
    ],
)
async def test_a_word_for_all_is_read_in_each_form_its_language_requires(
    query: str, ids: tuple[str, ...], gone: list[str]
) -> None:
    assert await _gone(query, ids) == gone


@pytest.mark.parametrize(
    ("query", "ids"),
    [
        ("Oublie tous les 4242, seulement la carte.", _FRENCH),
        ("Oublie tous les 4242, juste la carte.", _FRENCH),
        ("Olvida todas las 4242, solo la tarjeta.", _SPANISH),
        ("Olvida todas las 4242, la tarjeta sola.", _SPANISH),
        ("Olvida todo 4242.", _SPANISH),
        ("Olvida todos los 4242.", _SPANISH),
        ("Olvida toda 4242.", _SPANISH),
        ("Olvida 4242, la tarjeta también.", _SPANISH),
        ("Olvida el código 4242, mi teléfono también.", _SPANISH),
        ("Uită toate 4242.", _ROMANIAN),
        ("Uită toate 4242, doar cardul.", _ROMANIAN),
        ("Olvida 4242, la tarjeta también, solo el teléfono.", _SPANISH),
        ("Uită tot 4242.", _ROMANIAN),
        ("Uită codul 4242, cardul de asemenea.", _ROMANIAN),
        ("Vergiss alles 4242.", _GERMAN),
        ("Vergiss alle 4242, nur die Karte.", _GERMAN),
        ("Dimentica tutti i 4242, solo la card.", _ENGLISH),
        ("Esqueça todos os 4242.", _ENGLISH),
        ("Esqueça todo o 4242.", _ENGLISH),
        ("Verwijder alles 4242.", _ENGLISH),
    ],
)
async def test_a_word_whose_cell_is_empty_for_a_written_reason_lists_no_row(
    query: str, ids: tuple[str, ...]
) -> None:
    assert await _gone(query, ids) == []


@pytest.mark.parametrize(
    ("query", "ids", "text"),
    [
        ("Forget all 4242, card stays.", _ENGLISH, "card"),
        ("Oublie tout, la carte reste, seulement la carte.", _FRENCH, "carte"),
        ("Olvida todas, la tarjeta se queda, la tarjeta también.", _SPANISH, "tarjeta"),
        ("Uită toate, cardul rămâne, dulapul rămâne.", _ROMANIAN, "dulap"),
        ("Uită toate, cardul rămâne, doar cardul.", _ROMANIAN, "cardul"),
        ("Uită 4242 de pe card doar de pe dulap dar nu dulapul.", _ROMANIAN, "4242"),
        ("Uită 4242 doar de pe dulap exceptând dulapul.", _ROMANIAN, "4242"),
        ("Uită toate 4242, dulapul rămâne.", _ROMANIAN, "4242"),
        ("Uită tot, cardul rămâne, doar cardul.", _ROMANIAN, "cardul"),
    ],
)
async def test_a_row_the_message_keeps_stays_where_the_translated_word_is_unread(
    query: str, ids: tuple[str, ...], text: str
) -> None:
    assert await _gone(query, ids, text) == []


async def test_a_german_word_for_only_beside_an_added_row_lists_no_row_not_asked_for() -> None:
    assert await _gone("Vergiss alle 4242, die Karte auch, nur das Handy.", _GERMAN) == ["karte"]


async def test_a_french_word_for_only_beside_an_added_row_lists_no_row_not_asked_for() -> None:
    query = "Oublie tous les 4242, la carte aussi, seulement le téléphone."
    assert await _gone(query, _FRENCH) == ["carte"]


async def test_a_todo_row_is_named_by_its_word() -> None:
    assert await _gone("Forget the todo 4242.", ("locker", "card", "todo")) == ["todo"]
