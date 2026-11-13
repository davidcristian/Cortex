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
        ("My phone number was 0721 555 019.", _PHONE, "0721 555 018"),
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
    ],
)
async def test_a_statement_naming_no_other_value_of_its_fact_names_none(
    query: str, rows: tuple[str, ...], deleted: int
) -> None:
    assert await _held(query, *rows, deleted=deleted) == ""


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
