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
from cortex_core.memory_old_value import hold_old_value, old_value_note

_AT = datetime(2026, 11, 13, 6, 0, 0, tzinfo=UTC)
_ALARM = "User: Remember that my alarm code is 4826.\nAssistant: Noted."
_NUMBER = "User: Remember that my number is 0721 555 018.\nAssistant: Noted."
_PHONE = "User: My phone number is 0721 555 018.\nAssistant: Noted."


async def _rig(*texts: str) -> tuple[InMemoryMemoryStore, TurnCapabilities]:
    store = InMemoryMemoryStore()
    for index, text in enumerate(texts):
        embedding = tuple(await HashEmbedder().embed(text))
        await store.add(MemoryRecord(id=f"m{index}", text=text, embedding=embedding, at=_AT))
    return store, TurnCapabilities(memory=MemoryRecaller(store, HashEmbedder(), SystemClock()))


async def _held(query: str, *rows: str, deleted: int = 0, reply: str = "Got it.") -> str:
    _, caps = await _rig(*rows)
    taint = TaintLedger(forget_deleted=deleted)
    await hold_old_value(caps, taint, query=query, reply=reply, session_id="s")
    return taint.old_value


@pytest.mark.parametrize(
    ("query", "row", "value"),
    [
        ("My alarm code is now 5528.", _ALARM, "4826"),
        ("My birthday is actually 12 May.", "User: Remember that my birthday is 3 June.", "3 June"),
        ("My new number is 0721 555 019.", _NUMBER, "0721 555 018"),
        ("My current number is 0721 555 019.", _NUMBER, "0721 555 018"),
        ("My actual number is 0721 555 019.", _NUMBER, "0721 555 018"),
        ("My new phone number is 0721 555 019.", _PHONE, "0721 555 018"),
        ("My new number is 0721 555 019.", "User: My new number is 0721 555 018.", "0721 555 018"),
        ("My bike lock code is 4862.", "User: Remember that my bike lock code is 4826.", "4826"),
        (
            "Her phone is 0721 555 019.",
            "User: Remember that her phone is 0744 111 222.",
            "0744 111 222",
        ),
    ],
)
async def test_a_statement_of_a_stored_fact_with_another_value_names_the_old_value(
    query: str, row: str, value: str
) -> None:
    assert await _held(query, "User: Remember that my gym code is 1111.", row) == value


@pytest.mark.parametrize(
    ("query", "rows", "deleted"),
    [
        ("My alarm code is 4826.", (_ALARM,), 0),
        ("My alarm code is now 4826.", (_ALARM,), 0),
        ("My code is 5528.", (_ALARM,), 0),
        ("My number is 0721 555 019.", (_PHONE,), 0),
        ("My code is 4862 not 4826.", (_ALARM, "User: Remember that my code is 4242."), 0),
        ("My card is 4242.", ("User: Remember that my card is 4111 1111 1111 4242.",), 0),
        ("My bike code is 5528.", (_ALARM,), 0),
        ("My alarm code is now 5528.", (_ALARM,), 1),
        ("Is my alarm code 5528?", (_ALARM,), 0),
        ("My alarm code is 5528, not 1234.", (_ALARM,), 0),
        ("My alarm code is now 5528.", ("User: My alarm code is 4826, the old one.",), 0),
        (
            "My alarm code is now 5528.",
            ("User: Remember it.\nAssistant: Noted, her alarm code is 4826.",),
            0,
        ),
        ("My sister is vegan.", ("User: Remember that my sister is Ana.",), 0),
        ("My phone is broken.", ("User: Remember that my phone is 0744 111 222.",), 0),
        ("My flight is tomorrow.", ("User: Remember that my flight is LH 1234.",), 0),
        ("My kids are 5 and 7.", ("User: Remember that my kids are Ana and Ion.",), 0),
        ("Her phone is 0721 555 019.", ("User: Remember that my phone is 0744 111 222.",), 0),
        ("My phone is 0721 555 019.", ("User: Remember that his phone is 0744 111 222.",), 0),
        ("My number is 0721 555 019.", ("User: My new number is 0721 555 018.",), 0),
    ],
)
async def test_a_statement_naming_no_other_value_of_its_fact_names_none(
    query: str, rows: tuple[str, ...], deleted: int
) -> None:
    assert await _held(query, *rows, deleted=deleted) == ""


_MY_PHONE = "User: Remember that my phone is 0744 111 222."
_MY_NUMBER = "User: Remember that my phone number is 0721 555 019."


@pytest.mark.parametrize(
    ("query", "row"),
    [
        ("My work phone is 0721 555 019.", _MY_PHONE),
        ("My sister's phone is 0721 555 019.", _MY_PHONE),
        ("My phone at work is 0721 555 019.", _MY_PHONE),
        ("My gym code is 4242.", "User: Remember that my code is 1234."),
        ("My old phone number is 0744 111 222.", _MY_NUMBER),
        ("My old phone number was 0744 111 222.", _MY_NUMBER),
        ("My phone number was 0744 111 222.", _MY_NUMBER),
        ("My previous address was 12 Elm Street.", "User: Remember that my address is 3 Oak Road."),
        ("My old locker code was 1234.", "User: Remember that my locker code is 5528."),
        ("My phone number is 0744 111 222.", "User: My phone number was 0721 555 019."),
    ],
)
async def test_a_statement_of_another_or_a_past_fact_names_no_row(query: str, row: str) -> None:
    assert await _held(query, row) == ""


_DOOR = "User: Remember that my door code is 1987."


@pytest.mark.parametrize(
    ("query", "row", "value"),
    [
        ("My alarm code is 5528 now.", _ALARM, "4826"),
        ("My alarm code is 5528.", "User: My alarm code is now 4826. Thanks!", "4826"),
        ("My son is 6 years old.", "User: Remember that my son is 5 years old.", "5 years old"),
        ("My flight is LH 1234.", "User: Remember that my flight is LH 1200.", "LH 1200"),
        ("My kids are 6 and 8.", "User: Remember that my kids are 5 and 7.", "5 and 7"),
    ],
)
async def test_a_statement_of_one_sentence_names_the_old_value(
    query: str, row: str, value: str
) -> None:
    assert await _held(query, row) == value


@pytest.mark.parametrize(
    ("query", "row"),
    [
        ("My door code is also 7319.", _DOOR),
        ("Remember that my door code is also 7319.", _DOOR),
        ("My door code is 7319 too.", _DOOR),
        ("My door code is 7319 as well.", _DOOR),
        ("My door code is 7319 for the garage.", _DOOR),
        ("My pet is Rex. Room 12.", "User: My pet is 2 years old."),
        ("My PIN is 4242 off the record.", "User: Remember that my PIN is 1987."),
        ("My PIN is 4242. Off the record.", "User: Remember that my PIN is 1987."),
        ("My alarm code is 5528 or 5529.", _ALARM),
        ("My alarm code is 5528 and my door code is 1234.", _ALARM),
        ("My alarm code is 5528. My wife's alarm code is 4826.", _ALARM),
        ("My alarm code is 5528. Thanks, that is wrong.", _ALARM),
        ("My alarm code is 5528. Wait, that is wrong.", _ALARM),
        ("My alarm code is 5528. Just kidding.", _ALARM),
        ("My alarm code is 5528. My alarm code is 5528.", _ALARM),
        ("My alarm code is 5528. My door code is 1234.", _ALARM),
        ("Remember that my alarm code is 5528.\nNo, wait.", _ALARM),
        ("My alarm code is 4826.", "User: My alarm code is 4826. Thanks!"),
        ("My alarm code is ...", _ALARM),
        ("My alarm code is now.", _ALARM),
        ("My door code is 7319.", "User: Remember that my door code is also 1987."),
        ("My door code is also 7319.", "User: Remember that my door code is also 1987."),
        ("My birthday is on 12 May.", "User: Remember that my birthday is on 3 June."),
        ("Mon code de porte est aussi 7319.", "User: Retiens que mon code de porte est 1987."),
        ("Mein Türcode ist auch 7319.", "User: Merk dir, mein Türcode ist 1987."),
        ("Mi código de puerta es también 7319.", "User: Recuerda que mi código es 1987."),
        ("Codul meu de la ușă este și 7319.", "User: Reține că codul meu este 1987."),
    ],
)
async def test_a_second_value_or_sentence_names_no_old_value(query: str, row: str) -> None:
    assert await _held(query, row) == ""


async def test_an_unreadable_store_names_no_replaced_value() -> None:
    store, caps = await _rig(_ALARM)
    store.fail_with(MemoryStoreError("store down"))
    taint = TaintLedger()
    await hold_old_value(caps, taint, query="My alarm code is now 5528.", reply="", session_id="s")
    assert taint.old_value == ""


async def test_a_statement_turn_beside_the_old_row_ends_with_the_note() -> None:
    _, caps = await _rig(_ALARM)
    backend = ScriptedInferenceBackend([[TextChunk("Got it, your alarm code is 5528.")]])
    engine = TurnEngine(InMemorySessionStore(), backend, SystemClock(), capabilities=caps)
    events = engine.handle_turn("s", "My alarm code is now 5528.", turn_id="t")
    reply = "".join([event.text async for event in events if isinstance(event, TextDelta)])
    assert reply == "Got it, your alarm code is 5528." + old_value_note("4826", "en")


@pytest.mark.parametrize(
    "query",
    [
        "My alarm code is 5528 OFF THE RECORD.",
        "Save this: my alarm code is 5528 Off The Record.",
        "Remember my alarm code is 5528 Then Forget It.",
    ],
)
async def test_a_turn_asking_not_to_keep_a_new_value_records_nothing_and_names_the_old(
    query: str,
) -> None:
    _, caps = await _rig(_ALARM)
    assert caps.memory is not None
    backend = ScriptedInferenceBackend([[TextChunk("Understood.")]])
    engine = TurnEngine(InMemorySessionStore(), backend, SystemClock(), capabilities=caps)
    events = engine.handle_turn("s", query, turn_id="t")
    reply = "".join([event.text async for event in events if isinstance(event, TextDelta)])
    assert reply == "Understood." + old_value_note("4826", "en")
    assert await caps.memory.find_value("5528", session_id="s", limit=8) == ()


@pytest.mark.parametrize(
    "query",
    [
        "Save this: my alarm code is 5528.",
        "Store my alarm code 5528.",
        "Record that my alarm code is 5528.",
        "Remember that my alarm code is 5528.",
        "Please remember my alarm code is 5528.",
        "Remember this: my alarm code is 5528.",
        "Remember, my alarm code is 5528.",
        "Remember my alarm code 5528.",
        "Note that my alarm code is 5528.",
        "Keep in mind that my alarm code is 5528.",
        "Don't forget my alarm code is 5528.",
        "Write down my alarm code 5528.",
        "Save my new alarm code 5528.",
    ],
)
async def test_a_request_to_store_a_stored_fact_with_another_value_names_the_old_value(
    query: str,
) -> None:
    assert await _held(query, "User: Remember that my gym code is 1111.", _ALARM) == "4826"


@pytest.mark.parametrize(
    "query",
    [
        "Don't save my alarm code 5528.",
        "Don't store my alarm code 5528.",
        "Never record that my alarm code is 5528.",
        "Don't remember that my alarm code is 5528.",
        "Please don't save this: my alarm code is 5528.",
        "Remember not to save my alarm code 5528.",
        "Remember that my alarm code is not 5528.",
        "Save my door code 5528.",
        "Remember that my door code is 5528.",
        "Save my alarm code 4826.",
        "Remember that my alarm code is 4826.",
        "Store my alarm code was 5528.",
        "Remember that my alarm code was 5528.",
        "Remember that her alarm code is 5528.",
        "Remember that my alarm code is 5528?",
        "Remember to change my alarm code to 5528.",
        "Remember that my alarm code is 5528. Thanks for the help.",
        "Store my alarm code 5528 and my door code 1234.",
        "I always store my alarm code 5528 on paper.",
        "We record that my alarm code is 5528.",
        "My alarm code 5528.",
        "Remember.",
        "Save this: my alarm code is 5528 off the record.",
        "If I ask, remember that my alarm code is 5528.",
        "Remember my alarm code 5528 should be changed.",
        "Store my alarm code v2.",
    ],
)
async def test_a_request_that_stores_no_new_value_of_a_stored_fact_names_none(query: str) -> None:
    assert await _held(query, _ALARM) == ""


@pytest.mark.parametrize(
    ("query", "row"),
    [
        ("Save my draft 3.", "User: My draft is 2 pages."),
        ("Don't forget my card 4242.", "User: Remember that my card is 4111."),
        ("Store my code review 3.", "User: My code review is 2 days late."),
        ("Keep my volume at 40.", "User: My volume is 30."),
    ],
)
async def test_a_request_to_store_a_number_after_no_word_naming_a_value_names_none(
    query: str, row: str
) -> None:
    assert await _held(query, row) == ""


async def test_a_store_request_turn_beside_the_old_row_ends_with_the_note() -> None:
    _, caps = await _rig(_ALARM)
    backend = ScriptedInferenceBackend([[TextChunk("Saved, your alarm code is 5528.")]])
    engine = TurnEngine(InMemorySessionStore(), backend, SystemClock(), capabilities=caps)
    events = engine.handle_turn("s", "Save this: my alarm code is 5528.", turn_id="t")
    reply = "".join([event.text async for event in events if isinstance(event, TextDelta)])
    assert reply == "Saved, your alarm code is 5528." + old_value_note("4826", "en")


_CODE = "User: Remember that my code is 90909.\nAssistant: Noted."


@pytest.mark.parametrize(
    "query",
    [
        "Remember that my code is 5528. Thanks!",
        "Remember that my code is 5528, thanks.",
        "Remember that my code is 5528. Thank you!",
        "My code is 5528. Thanks!",
        "My code is now 5528, thank you.",
    ],
)
async def test_a_statement_closed_by_thanks_names_the_old_value(query: str) -> None:
    assert await _held(query, _CODE) == "90909"


async def test_a_value_ending_in_thanks_keeps_its_last_word() -> None:
    row = "User: Remember that my password is Pass4."
    assert await _held("Remember that my password is Pass4thanks.", row) == "Pass4"


@pytest.mark.parametrize(
    ("query", "row"),
    [
        ("Remember that my code is thanks 5528.", _CODE),
        ("Remember that my password is Thanks.", "User: Remember that my password is 90909."),
        ("Remember that my code is 5528. Thanks for changing it!", _CODE),
        ("Remember that my code is 5528. Thanks, and my gym code is 1234.", _CODE),
        ("Remember that my gym code is 5528. Thanks!", _CODE),
        ("Remember that my code is 5528. Thanks, not 1234!", _CODE),
        ("Thanks! Remember that my code is 5528.", _CODE),
    ],
)
async def test_a_thanks_that_does_not_close_a_statement_of_the_fact_names_none(
    query: str, row: str
) -> None:
    assert await _held(query, row) == ""
