from datetime import UTC, datetime, timedelta

import pytest

from cortex_core import (
    FORGET_CHOSEN_TOOL_NAME,
    GLOBAL_MEMORY_SCOPE,
    ForgetChosenTool,
    HashEmbedder,
    InMemoryMemoryStore,
    MemoryRecaller,
    MemoryRecord,
    SystemClock,
    TaintLedger,
    ToolCall,
    ToolRun,
    TurnCapabilities,
)
from cortex_core.closing_notes import limit_notes
from cortex_core.memory_claim import UNKEPT_CLAIM_NOTE, names_spared
from cortex_core.stops import StopLedger
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 9, 7, 0, 0, tzinfo=UTC)
_BIKE = "User: Remember that my bike lock code is 7319.\nAssistant: Noted."
_SHED = "User: Remember that the shed padlock code is also 7319.\nAssistant: Noted."
_SPARED = ("User: Remember that the shed padlock code is also 7319. Assistant: Noted.",)
_QUERY = "Forget my bike lock code 7319, keep the shed one."

NAMES_A_KEPT_ROW = [
    "Done, I've forgotten your bike lock code and kept the shed one.",
    "I've forgotten your bike lock code and kept your shed padlock code in memory.",
    "I've deleted the bike lock code and kept the shed padlock code, as you asked.",
]
CLAIMS_MORE = [
    "I've forgotten the bike lock code and saved your message.",
    "I've forgotten the bike lock code and noted what you asked me to remember.",
    "I've forgotten the bike lock code and kept the shed code and noted that you like tea.",
    "Done, I've forgotten your bike lock code and kept the gym one.",
    "I've forgotten the bike lock code and noted the assistant's reply.",
    "I've forgotten the bike lock code. I've updated your shed padlock code to 7319.",
    "I've forgotten the bike lock code and noted your shed padlock code.",
    "I've forgotten the bike lock code and kept what you asked me to remember in memory.",
    "I've forgotten the bike lock code and kept the assistant's reply in memory.",
]


@pytest.mark.parametrize("reply", NAMES_A_KEPT_ROW)
def test_a_reply_keeping_only_a_row_the_forget_kept_names_it(reply: str) -> None:
    assert names_spared(reply, _SPARED)
    assert not names_spared(reply, ())


@pytest.mark.parametrize("reply", CLAIMS_MORE)
def test_a_reply_claiming_to_keep_anything_else_names_no_kept_row(reply: str) -> None:
    assert not names_spared(reply, _SPARED)


def test_a_reply_claiming_no_keep_names_no_kept_row() -> None:
    assert not names_spared("I've forgotten your bike lock code.", _SPARED)


def _closed(reply: str, spared: tuple[str, ...]) -> str:
    recaller = MemoryRecaller(InMemoryMemoryStore(), HashEmbedder(), SystemClock())
    parts = [reply]
    taint = TaintLedger(forget_asked=True, forget_calls=1, forget_deleted=1, forget_spared=spared)
    runs = (ToolRun(name=FORGET_CHOSEN_TOOL_NAME, ok=True),)
    caps = TurnCapabilities(memory=recaller)
    list(limit_notes(StopLedger(), runs, parts, caps=caps, taint=taint, query=_QUERY))
    return "".join(parts)


@pytest.mark.parametrize("reply", NAMES_A_KEPT_ROW)
def test_a_forget_reply_keeping_the_row_the_forget_kept_gets_no_unkept_note(reply: str) -> None:
    assert UNKEPT_CLAIM_NOTE not in _closed(reply, _SPARED)
    assert UNKEPT_CLAIM_NOTE in _closed(reply, ())


@pytest.mark.parametrize("reply", CLAIMS_MORE)
def test_a_forget_reply_claiming_another_keep_keeps_the_unkept_note(reply: str) -> None:
    assert UNKEPT_CLAIM_NOTE in _closed(reply, _SPARED)


def _row(record_id: str, text: str, minutes: int) -> MemoryRecord:
    at = _AT + timedelta(minutes=minutes)
    return MemoryRecord(id=record_id, text=text, embedding=(1.0, 0.0), at=at)


def _call(call_id: str, text: str, query: str) -> ToolCall:
    stamp = TurnStamp(session_id="chat-a", turn_id="t1", query=query)
    return ToolCall(id=call_id, name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text}, stamp=stamp)


async def test_a_forget_reports_every_row_it_kept_until_a_later_call_deletes_it() -> None:
    store = InMemoryMemoryStore()
    await store.add(_row("bike", _BIKE, 0))
    await store.add(_row("shed", _SHED, 1))
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    first = _call("c1", "7319", _QUERY)
    await tool.card(first)
    kept = await tool.invoke(first)
    assert (kept.spared, kept.kept, kept.forgot) == (_SPARED, (), 1)
    later = _call("c2", "shed padlock", _QUERY)
    assert await tool.card(later) is not None
    assert (await tool.invoke(later)).spared == ()


async def test_a_forget_that_kept_every_row_reports_them_as_kept_and_spared() -> None:
    store = InMemoryMemoryStore()
    await store.add(_row("shed", _SHED, 1))
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    call = _call("c1", "7319", "Forget 7319, keep the shed one.")
    assert await tool.card(call) is None
    result = await tool.invoke(call)
    assert result.spared == result.kept == _SPARED
