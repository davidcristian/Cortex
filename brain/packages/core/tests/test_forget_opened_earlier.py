from dataclasses import replace

import pytest

from cortex_core import (
    FORGET_CHOSEN_TOOL_NAME,
    FORGET_NOT_KEPT_NOTE,
    GLOBAL_MEMORY_SCOPE,
    UNKEPT_CLAIM_NOTE,
    CompositeToolRegistry,
    DispatchPolicy,
    ForgetChosenTool,
    HashEmbedder,
    InMemoryMemoryStore,
    InMemorySessionStore,
    MemoryRecaller,
    RecordingAuditSink,
    RecordingConfirmer,
    SystemClock,
    TaintLedger,
    ToolCall,
    ToolDispatcher,
    ToolResult,
    ToolRun,
    TurnCapabilities,
    memory_withheld,
)
from cortex_core.closing_notes import limit_notes
from cortex_core.forget_opened_earlier import keeps_unmatched, opened_earlier
from cortex_core.stops import StopLedger
from cortex_core.tools import TurnStamp
from cortex_core.turn_output import record_exchange

_ALARM = "User: Remember that my alarm code is 4242.\nAssistant: I've noted your alarm code 4242."
_PHONE = "User: Remember that my phone number is 0721 555 4242.\nAssistant: Noted."
_GARAGE = "User: Remember that my alarm code is 4242 for the garage.\nAssistant: Noted."
_NO_VALUE = "User: Remember that my alarm is on.\nAssistant: Noted."
_STATED = "My alarm code is 5528."
_NOTED = "I've noted that your alarm code is 5528."
_RAN = ToolRun(name=FORGET_CHOSEN_TOOL_NAME, ok=True)
_FAILED = ToolRun(name=FORGET_CHOSEN_TOOL_NAME, ok=False)

STATEMENTS = (
    "My alarm code is 5528.",
    "My phone number is 0721 555 9876.",
    "My locker code is 7319.",
)
NEAR_MISSES = (
    "Vergeet alsjeblieft mijn pincode 5521.",
    "Mein Alarmcode ist 5528.",
    "Scrap 9999.",
    "Scrap the code 4242.",
    "Cancel the code I gave you.",
    "My alarm code is 5528, not 4242.",
    "My alarm code is no longer 4242.",
    "My new code is 5528, drop the old one.",
    "Remember my PIN 1234. Actually, forget it.",
    "Forget 4242. My alarm code is 5528.",
    "What is my alarm code?",
    "Can you do the same with my PIN 4821?",
    "What about my PIN 4821?",
    "And the PIN, 4821?",
    "My PIN is 4821. What about that one?",
)


@pytest.mark.parametrize("query", STATEMENTS)
def test_a_message_that_alone_would_have_the_forget_refused_was_opened_earlier(
    query: str,
) -> None:
    assert opened_earlier(query)


@pytest.mark.parametrize("query", NEAR_MISSES)
def test_a_message_that_may_ask_to_forget_was_not_opened_earlier(query: str) -> None:
    assert not opened_earlier(query)


@pytest.mark.parametrize(
    ("matched_nothing", "query", "kept"),
    [(True, _STATED, True), (False, _STATED, False), (True, NEAR_MISSES[0], False)],
)
def test_only_an_unmatched_forget_on_a_message_opened_earlier_keeps_the_turn(
    *, matched_nothing: bool, query: str, kept: bool
) -> None:
    result = ToolResult(call_id="f", content="nothing.", matched_nothing=matched_nothing)
    assert keeps_unmatched(result, query) is kept


def _caps() -> TurnCapabilities:
    recaller = MemoryRecaller(InMemoryMemoryStore(), HashEmbedder(), SystemClock())
    return TurnCapabilities(memory=recaller)


def _unmatched(calls: int = 1, unmatched: int = 1) -> TaintLedger:
    return TaintLedger(forget_asked=True, forget_calls=calls, forget_unmatched=unmatched)


def _deleted(*gone: str, deleted: int = 1) -> TaintLedger:
    return TaintLedger(forget_asked=True, forget_calls=1, forget_deleted=deleted, forget_gone=gone)


@pytest.mark.parametrize(
    ("taint", "runs", "query", "withheld"),
    [
        (_unmatched(), (_RAN,), _STATED, False),
        (_unmatched(2, 2), (_RAN, _RAN), STATEMENTS[1], False),
        (_unmatched(), (_RAN,), STATEMENTS[2], False),
        *((_unmatched(), (_RAN,), query, True) for query in NEAR_MISSES),
        (_unmatched(2, 1), (_RAN, _RAN), _STATED, True),
        (_unmatched(2, 1), (_RAN,), _STATED, True),
        (_unmatched(1, 0), (_RAN,), _STATED, True),
        (_unmatched(), (_RAN, _RAN), _STATED, True),
        (_unmatched(), (), _STATED, True),
        (TaintLedger(forget_asked=True), (), _STATED, True),
    ],
)
def test_a_forget_that_matched_nothing_keeps_a_message_opened_earlier(
    *, taint: TaintLedger, runs: tuple[ToolRun, ...], query: str, withheld: bool
) -> None:
    assert memory_withheld(_caps(), taint, runs, query=query, reply=_NOTED) is withheld


@pytest.mark.parametrize(
    ("taint", "runs", "query", "reply", "withheld"),
    [
        (_deleted(_ALARM), (_RAN,), _STATED, _NOTED, False),
        (_deleted(_PHONE), (_RAN,), STATEMENTS[1], "I've noted 0721 555 9876.", False),
        (_deleted(_ALARM), (_RAN,), _STATED, "I've noted 5528 in place of 4242.", True),
        (_deleted(_PHONE), (_RAN,), STATEMENTS[1], "I've noted it, not 0721-555-4242.", True),
        (_deleted(_ALARM), (_RAN,), _STATED, "I've noted 5528 and your door code 42420.", True),
        (_deleted(_GARAGE), (_RAN,), _STATED, "I've noted 5528 for the garage.", True),
        (_deleted(_GARAGE), (_RAN,), _STATED, _NOTED, True),
        (_deleted(_GARAGE), (_RAN,), "My garage alarm code is 5528.", _NOTED, False),
        (_deleted(_NO_VALUE), (_RAN,), _STATED, _NOTED, True),
        (_deleted(_ALARM, deleted=2), (_RAN,), _STATED, _NOTED, True),
        (replace(_deleted(_ALARM), forget_declined=True), (_RAN,), _STATED, _NOTED, True),
        (replace(_deleted(_ALARM), forget_spared=("a row",)), (_RAN,), _STATED, _NOTED, True),
        (_deleted(_ALARM), (_RAN, _FAILED), _STATED, _NOTED, True),
        (_deleted(_ALARM), (_RAN,), _STATED, "I've removed the old code.", True),
        (_deleted(_ALARM), (_RAN,), _STATED, "", True),
        (_deleted(_ALARM), (_RAN,), NEAR_MISSES[1], _NOTED, True),
        (_deleted(_ALARM), (_RAN,), NEAR_MISSES[9], _NOTED, True),
        (_deleted(_ALARM), (), _STATED, _NOTED, True),
        (_deleted(), (_RAN,), _STATED, _NOTED, True),
    ],
)
def test_a_forget_that_deleted_a_row_keeps_only_an_exchange_restating_none_of_it(
    *, taint: TaintLedger, runs: tuple[ToolRun, ...], query: str, reply: str, withheld: bool
) -> None:
    assert memory_withheld(_caps(), taint, runs, query=query, reply=reply) is withheld


@pytest.mark.parametrize(("reply", "shown"), [(_NOTED, False), ("I've noted 4242.", True)])
def test_the_unkept_note_shows_only_on_a_turn_that_stores_nothing(
    *, reply: str, shown: bool
) -> None:
    parts = [reply]
    taint = _deleted(_ALARM)
    list(limit_notes(StopLedger(), (_RAN,), parts, caps=_caps(), taint=taint, query=_STATED))
    assert (UNKEPT_CLAIM_NOTE in "".join(parts)) is shown


@pytest.mark.parametrize(("reply", "stored"), [(_NOTED, 1), ("I've noted 4242.", 0)])
async def test_a_turn_that_restates_nothing_it_deleted_is_recorded(
    *, reply: str, stored: int
) -> None:
    store = InMemoryMemoryStore()
    caps = TurnCapabilities(memory=MemoryRecaller(store, HashEmbedder(), SystemClock()))
    await record_exchange(
        caps,
        _deleted(_ALARM),
        store=InMemorySessionStore(),
        session_id="s",
        query=_STATED,
        reply=reply,
        runs=(_RAN,),
    )
    assert len(await store.search(await HashEmbedder().embed(_STATED), k=5)) == stored


@pytest.mark.parametrize(
    ("query", "noted"), [(_STATED, False), (NEAR_MISSES[0], True), (NEAR_MISSES[11], True)]
)
async def test_an_unmatched_forget_result_says_nothing_is_kept_only_when_that_may_be_true(
    *, query: str, noted: bool
) -> None:
    forget = ForgetChosenTool(InMemoryMemoryStore(), GLOBAL_MEMORY_SCOPE)
    dispatcher = ToolDispatcher(
        CompositeToolRegistry([forget]),
        RecordingAuditSink(),
        SystemClock(),
        confirmer=RecordingConfirmer(answer=True),
        policy=DispatchPolicy(
            record_cards={FORGET_CHOSEN_TOOL_NAME: forget}, notes={FORGET_CHOSEN_TOOL_NAME: forget}
        ),
    )
    call = ToolCall(id="f", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": "5528"})
    stamp = TurnStamp(session_id="s", query=query)
    result = await dispatcher.dispatch(call, stamp=stamp, confirm_required=True)
    assert result.matched_nothing
    assert (FORGET_NOT_KEPT_NOTE in result.content) is noted
