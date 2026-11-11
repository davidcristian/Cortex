from datetime import UTC, datetime

import pytest

from cortex_core import (
    HashEmbedder,
    InMemoryMemoryStore,
    InMemorySessionStore,
    MemoryRecaller,
    MemoryRecord,
    MemoryStoreError,
    ScriptedInferenceBackend,
    SystemClock,
    TaintLedger,
    TextChunk,
    TextDelta,
    TurnCapabilities,
    TurnEngine,
)
from cortex_core.memory_old_value import (
    OLD_VALUE_NOTE,
    OLD_VALUE_NOTES,
    claims_changed,
    corrected_values,
    hold_old_value,
    holds,
    old_value_note,
)
from cortex_core.note_language import message_language

_AT = datetime(2026, 11, 11, 3, 0, 0, tzinfo=UTC)
_SEED = "User: Remember that my bike lock code is 4826.\nAssistant: Noted."
_CORRECTION = "My bike lock code is 4862, not 4826."
_UPDATED = "I've updated that for you. Your bike lock code is 4862."


@pytest.mark.parametrize(
    ("message", "values"),
    [
        (_CORRECTION, ("4826",)),
        ("My sister's name is Hannah, not Anna.", ("Anna",)),
        ("My phone is 0170 5555, not 015 123 456 789. Remember it.", ("015 123 456 789",)),
        ("Change my phone from 015 123 456 789 to 0170 5555.", ("015 123 456 789",)),
        ("Replace 4826 with 4862.", ("4826",)),
        ("4826 is wrong, my code is 4862.", ("4826",)),
        ("Update my phone: 0170 5555 instead of 015 123 456 789.", ("015 123 456 789",)),
        ("My phone is no longer 015.123.456, it is 0170 5555.", ("015.123.456",)),
        ("Mon code est 4862, pas 4826.", ("4826",)),
        ("Mein Code ist 4862, nicht 4826.", ("4826",)),
        ("Mi código es 4862, no 4826.", ("4826",)),
        ("Codul meu este 4862, nu 4826.", ("4826",)),
        ("Move my dentist to 10:00, not 9:00.", ("9:00",)),
        ("Change the dentist from 9:00 to 10:00.", ("9:00",)),
        ("I moved from Berlin to Paris.", ("Berlin",)),
        ("My code is 4862, no 4826.", ("4826",)),
        ("Este 4417, nu 4471.", ("4471",)),
        ("It is 4862, not 4826.", ("4826",)),
        ("Is it 4862? It is 4862, not 4826.", ("4826",)),
    ],
)
def test_a_correction_names_its_old_value(message: str, values: tuple[str, ...]) -> None:
    assert corrected_values(message) == values


@pytest.mark.parametrize(
    "message",
    [
        "My bike lock code is 4862.",
        "Is my code 4862 or 4826?",
        "I am not sure, my code is 4862.",
        "It is 4862, not the old one.",
        "My code is 4862, not just any code.",
        "That is wrong, my code is 4862.",
        "The code is wrong, it is 4862.",
        "Move it from tomorrow to Friday.",
        "My code is 4862 not 4826.",
        "Remember I work from 9 to 5.",
        "Remember I fly from Berlin to Paris on Friday.",
        "Remember my trip is from 12.03 to 15.03.",
        "Remember the movie runs from 9 to 11.",
        "Ok, no problem, remember my code is 4862.",
        "Remember my code is 4862. Thanks, no rush.",
        "Da, nu știu.",
        "I moved last year, not because I wanted to.",
        "Is my code 4862, not 4826?",
        "Mi color es azul, no verde.",
        "Was it changed from 9:00 to 10:00?",
        "Ok, not Monday?",
        "Is my code 4862, not 4826? Just checking.",
    ],
)
def test_a_message_naming_no_old_value_names_none(message: str) -> None:
    assert corrected_values(message) == ()


def test_a_value_named_twice_is_named_once() -> None:
    assert corrected_values("It is 4862, not 4826. Again: 4862, not 4826.") == ("4826",)


@pytest.mark.parametrize(
    ("text", "value", "held"),
    [
        (_SEED, "4826", True),
        ("User: my phone is 015123456789", "015 123 456 789", True),
        ("User: my phone is 015-123-456-789", "015 123 456 789", True),
        ("User: my sister is Hannah", "Anna", False),
        ("User: my code is 48261", "4826", False),
        ("User: my code is 14826", "4826", False),
        ("User: my code is 4826.", "4826", True),
        ("User: my dentist is at 9:00.", "9:00", True),
        ("User: my locker is number 9.", "9:00", False),
        ("User: my dentist is at 19:00.", "9:00", False),
    ],
)
def test_a_row_holds_a_value_only_whole(text: str, value: str, *, held: bool) -> None:
    assert holds(text, value) is held


@pytest.mark.parametrize(
    ("reply", "claimed"),
    [
        (_UPDATED, True),
        ("I've noted that your code is 4862.", False),
        ("I haven't updated anything.", False),
        ("J'ai mis à jour votre code : 4862.", True),
        ("Votre code a été modifié.", True),
        ("Je n'ai pas modifié votre code.", False),
        ("Ich habe Ihren Code auf 4862 aktualisiert.", True),
        ("Der Code wurde geändert.", True),
        ("Ich habe den Code nicht geändert.", False),
        ("He actualizado tu código a 4862.", True),
        ("¿Lo he cambiado?", False),
        ("Am actualizat codul tău la 4862.", True),
        ("Codul a fost schimbat.", True),
        ("Nu am schimbat codul.", False),
    ],
)
def test_a_reply_claims_a_change_in_five_languages(reply: str, *, claimed: bool) -> None:
    assert claims_changed(reply) is claimed


async def _rig(*texts: str) -> tuple[InMemoryMemoryStore, TurnCapabilities]:
    store = InMemoryMemoryStore()
    for index, text in enumerate(texts):
        embedding = tuple(await HashEmbedder().embed(text))
        await store.add(MemoryRecord(id=f"m{index}", text=text, embedding=embedding, at=_AT))
    return store, TurnCapabilities(memory=MemoryRecaller(store, HashEmbedder(), SystemClock()))


async def _held(caps: TurnCapabilities, taint: TaintLedger, query: str, reply: str) -> str:
    await hold_old_value(caps, taint, query=query, reply=reply, session_id="s")
    return taint.old_value


async def test_an_update_claim_while_a_row_holds_the_old_value_names_it() -> None:
    _, caps = await _rig("User: Remember that my bike lock code is 48261.", _SEED)
    assert await _held(caps, TaintLedger(), _CORRECTION, _UPDATED) == "4826"


@pytest.mark.parametrize(
    ("query", "reply", "deleted"),
    [
        (_CORRECTION, _UPDATED, 1),
        (_CORRECTION, "Got it, your code is 4862.", 0),
        ("My bike lock code is 4862.", _UPDATED, 0),
        ("My bike lock code is 4862, not 1111.", _UPDATED, 0),
    ],
)
async def test_no_old_value_is_named_unless_every_condition_holds(
    query: str, reply: str, deleted: int
) -> None:
    _, caps = await _rig(_SEED)
    assert await _held(caps, TaintLedger(forget_deleted=deleted), query, reply) == ""


@pytest.mark.parametrize(
    "reply",
    [
        "Noted, your bike lock code is 4862.",
        "OK. I've noted that your bike lock code is **4862**, not 4826.",
        "I'll remember that your code is 4862.",
        "C'est noté, votre code est 4862.",
    ],
)
async def test_a_kept_claim_while_a_row_holds_the_old_value_names_it(reply: str) -> None:
    _, caps = await _rig(_SEED, f"User: {_CORRECTION}\nAssistant: {reply}")
    assert await _held(caps, TaintLedger(), _CORRECTION, reply) == "4826"


@pytest.mark.parametrize(
    ("reply", "deleted"),
    [
        ("Should I note 4862 as your code?", 0),
        ("I have not noted anything.", 0),
        ("Your code is 4862.", 0),
        ("Noted, your bike lock code is 4862.", 1),
    ],
)
async def test_a_reply_asking_restating_or_after_a_delete_names_no_old_value(
    reply: str, deleted: int
) -> None:
    _, caps = await _rig(_SEED)
    assert await _held(caps, TaintLedger(forget_deleted=deleted), _CORRECTION, reply) == ""


@pytest.mark.parametrize(
    ("query", "held"),
    [
        ("Remember I fly from Berlin to Paris on Friday.", ""),
        ("Move my dentist to 10:00, not 9:00.", ""),
        ("I moved from Berlin to Paris.", "Berlin"),
    ],
)
async def test_a_route_or_a_clock_time_names_no_unrelated_row(query: str, held: str) -> None:
    _, caps = await _rig("User: I live in Berlin.\nAssistant: Noted.", "User: My locker is 9.")
    assert await _held(caps, TaintLedger(), query, "Noted, I've updated that.") == held


async def test_a_row_naming_the_value_as_wrong_does_not_hold_it() -> None:
    _, caps = await _rig(f"User: {_CORRECTION}\nAssistant: Noted.")
    assert await _held(caps, TaintLedger(), _CORRECTION, _UPDATED) == ""


async def test_no_memory_or_an_unreadable_store_names_no_old_value() -> None:
    assert await _held(TurnCapabilities(), TaintLedger(), _CORRECTION, _UPDATED) == ""
    store, caps = await _rig(_SEED)
    store.fail_with(MemoryStoreError("store down"))
    assert await _held(caps, TaintLedger(), _CORRECTION, _UPDATED) == ""


@pytest.mark.parametrize(
    ("message", "language"),
    [
        ("Mon code de vélo est 4862, pas 4826. Merci beaucoup.", "fr"),
        ("Mein Fahrradcode ist 4862, nicht 4826. Ich danke dir.", "de"),
        ("Mi código de la bici es 4862, no 4826. Muchas gracias.", "es"),
        ("Codul meu de bicicletă este 4862, nu 4826. Mulțumesc mult.", "ro"),
    ],
)
def test_the_note_names_the_value_in_the_message_language(message: str, language: str) -> None:
    assert message_language(message) == language
    note = old_value_note(corrected_values(message)[0], message_language(message))
    assert note == OLD_VALUE_NOTES[language].format(value="4826")


def test_an_english_message_gets_the_english_note() -> None:
    assert old_value_note("4826", message_language(_CORRECTION)) == OLD_VALUE_NOTE.format(
        value="4826"
    )


async def test_a_correction_turn_claiming_an_update_ends_with_the_note() -> None:
    _, caps = await _rig(_SEED)
    backend = ScriptedInferenceBackend([[TextChunk(_UPDATED)]])
    engine = TurnEngine(InMemorySessionStore(), backend, SystemClock(), capabilities=caps)
    events = engine.handle_turn("s", _CORRECTION, turn_id="t")
    reply = "".join([event.text async for event in events if isinstance(event, TextDelta)])
    assert reply == _UPDATED + old_value_note("4826", "en")


async def test_a_french_correction_turn_ends_with_the_french_note() -> None:
    _, caps = await _rig("User: Retiens que mon code est 4826.\nAssistant: Noté.")
    backend = ScriptedInferenceBackend([[TextChunk("J'ai mis à jour votre code.")]])
    engine = TurnEngine(InMemorySessionStore(), backend, SystemClock(), capabilities=caps)
    events = engine.handle_turn("s", "Mon code est 4862, pas 4826.", turn_id="t")
    reply = "".join([event.text async for event in events if isinstance(event, TextDelta)])
    assert reply.endswith(old_value_note("4826", "fr"))


async def test_a_correction_turn_claiming_it_noted_the_value_ends_with_the_note() -> None:
    _, caps = await _rig(_SEED)
    noted = "Noted, your bike lock code is 4862."
    backend = ScriptedInferenceBackend([[TextChunk(noted)]])
    engine = TurnEngine(InMemorySessionStore(), backend, SystemClock(), capabilities=caps)
    events = engine.handle_turn("s", _CORRECTION, turn_id="t")
    reply = "".join([event.text async for event in events if isinstance(event, TextDelta)])
    assert reply.startswith(noted)
    assert old_value_note("4826", "en") in reply
