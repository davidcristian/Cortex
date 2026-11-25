from datetime import UTC, datetime

import pytest

from cortex_core import (
    HashEmbedder,
    InMemoryMemoryStore,
    InMemorySessionStore,
    MemoryRecaller,
    MemoryRecord,
    ScriptedInferenceBackend,
    SystemClock,
    TaintLedger,
    TextChunk,
    TextDelta,
    TurnCapabilities,
    TurnEngine,
)
from cortex_core.memory_old_value import hold_old_value, old_value_note

_AT = datetime(2026, 11, 25, 6, 0, 0, tzinfo=UTC)
_FR = "User: Mon code d'alarme est 4826.\nAssistant: Noté."
_FR_ASKED = "User: Retiens que mon code d'alarme est 4826.\nAssistant: Noté."
_DE = "User: Mein Alarmcode ist 4826.\nAssistant: Notiert."
_DE_DASS = "User: Merk dir, dass mein Alarmcode 4826 ist.\nAssistant: Notiert."
_ES = "User: Mi código de alarma es 4826.\nAssistant: Anotado."
_RO = "User: Codul meu de alarmă este 4826.\nAssistant: Notat."
_RO_ASKED = "User: Reține că codul meu de alarmă este 4826.\nAssistant: Notat."


async def _held(query: str, *rows: str) -> str:
    store = InMemoryMemoryStore()
    for index, text in enumerate(rows):
        embedding = tuple(await HashEmbedder().embed(text))
        await store.add(MemoryRecord(id=f"m{index}", text=text, embedding=embedding, at=_AT))
    caps = TurnCapabilities(memory=MemoryRecaller(store, HashEmbedder(), SystemClock()))
    taint = TaintLedger()
    await hold_old_value(caps, taint, query=query, reply="Got it.", session_id="s")
    return taint.old_value


@pytest.mark.parametrize(
    ("query", "row"),
    [
        ("Mon code d'alarme est 5528.", _FR),
        ("Retiens que mon code d'alarme est 5528.", _FR),
        ("Souviens-toi que mon code d'alarme est 5528.", _FR_ASKED),
        ("Mein Alarmcode ist 5528.", _DE),
        ("Merk dir, dass mein Alarmcode 5528 ist.", _DE),
        ("Mein Alarmcode ist 5528.", _DE_DASS),
        ("Merk dir, dass mein Alarmcode 5528 ist.", _DE_DASS),
        ("Mi código de alarma es 5528.", _ES),
        ("Recuerda que mi código de alarma es 5528.", _ES),
        ("Codul meu de alarmă este 5528.", _RO),
        ("Reține că codul meu de alarmă este 5528.", _RO),
        ("Codul meu de alarmă e 5528.", _RO_ASKED),
    ],
)
async def test_a_new_value_stated_in_another_language_names_the_old_value(
    query: str, row: str
) -> None:
    assert await _held(query, row) == "4826"


async def test_a_value_of_several_words_after_dass_names_the_old_value() -> None:
    row = "User: Meine Telefonnummer ist 0721 555 018."
    query = "Merk dir, dass meine Telefonnummer 0721 555 019 ist."
    assert await _held(query, row) == "0721 555 018"


@pytest.mark.parametrize(
    ("query", "row"),
    [
        ("Mon code d'alarme est pas 5528.", _FR),
        ("Mein Alarmcode ist nicht 5528.", _DE),
        ("Mi código de alarma no es 5528.", _ES),
        ("Codul meu de alarmă nu este 5528.", _RO),
        ("Mon code de vélo est 5528.", _FR),
        ("Mein Fahrradcode ist 5528.", _DE),
        ("Mi código de bici es 5528.", _ES),
        ("Codul meu de bicicletă este 5528.", _RO),
        ("Notre code d'alarme est 5528.", _FR),
        ("Unser Alarmcode ist 5528.", _DE),
        ("Nuestro código de alarma es 5528.", _ES),
        ("Codul nostru de alarmă este 5528.", _RO),
        ("Mon code d'alarme est 4826.", _FR),
        ("Merk dir, dass mein Alarmcode 4826 ist.", _DE),
        ("Mi código de alarma es 4826.", _ES),
        ("Codul meu de alarmă este 4826.", _RO),
        ("Mon code d'alarme est maintenant 5528.", _FR),
        ("Mon nouveau code d'alarme est 5528.", _FR),
        ("Mein Alarmcode ist jetzt 5528.", _DE),
        ("Merk dir, dass mein Alarmcode jetzt 5528 ist.", _DE),
        ("Mein neuer Alarmcode ist 5528.", _DE),
        ("Mein Alarmcode ist 5528 ist.", "User: Mein Alarmcode ist 4826 ist."),
        ("Numărul meu de alarmă este 5528.", _RO),
        ("Mon code d'alarme est 5528.", _DE),
        ("Mein Alarmcode ist 5528.", _FR),
        ("Mon code d'alarme est 5528. Mon code de porte est 1234.", _FR),
        ("Il mio codice d'allarme è 5528.", "User: Il mio codice d'allarme è 4826."),
        ("Ricorda che il mio codice d'allarme è 5528.", "User: Il mio codice d'allarme è 4826."),
        ("O meu código de alarme é 5528.", "User: O meu código de alarme é 4826."),
        ("Lembra que o meu código de alarme é 5528.", "User: O meu código de alarme é 4826."),
        ("Mijn alarmcode is 5528.", "User: Mijn alarmcode is 4826."),
        ("Onthoud dat mijn alarmcode 5528 is.", "User: Onthoud dat mijn alarmcode 4826 is."),
        ("Mój kod alarmu to 5528.", "User: Mój kod alarmu to 4826."),
        ("Zapamiętaj, że mój kod alarmu to 5528.", "User: Mój kod alarmu to 4826."),
    ],
)
async def test_a_statement_naming_no_new_value_of_the_stored_fact_names_none(
    query: str, row: str
) -> None:
    assert await _held(query, row) == ""


async def test_a_german_statement_turn_beside_the_old_row_ends_with_the_german_note() -> None:
    store = InMemoryMemoryStore()
    embedding = tuple(await HashEmbedder().embed(_DE))
    await store.add(MemoryRecord(id="m0", text=_DE, embedding=embedding, at=_AT))
    caps = TurnCapabilities(memory=MemoryRecaller(store, HashEmbedder(), SystemClock()))
    backend = ScriptedInferenceBackend([[TextChunk("Notiert, dein Alarmcode ist 5528.")]])
    engine = TurnEngine(InMemorySessionStore(), backend, SystemClock(), capabilities=caps)
    query = "Merk dir, dass mein Alarmcode 5528 ist."
    events = engine.handle_turn("s", query, turn_id="t")
    reply = "".join([event.text async for event in events if isinstance(event, TextDelta)])
    assert reply == "Notiert, dein Alarmcode ist 5528." + old_value_note("4826", "de")
