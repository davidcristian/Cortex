from collections.abc import Sequence

import pytest

from cortex_core import (
    FORGET_CHOSEN_TOOL_NAME,
    FORGET_UNTRUSTED_TOOL_NAME,
    UNKEPT_CLAIM_NOTE,
    HashEmbedder,
    InMemoryMemoryStore,
    MemoryRecaller,
    SystemClock,
    TaintLedger,
    ToolRun,
    TurnCapabilities,
)
from cortex_core.closing_notes import limit_notes
from cortex_core.stops import StopLedger

_NEW_VALUE = "Note that my phone number is now 0699000000, and delete the old one."
_PLAIN = "Remember that my locker code is 8426."
_REPLY = "Your phone number is 0699000000."
_DELETED = ToolRun(name=FORGET_CHOSEN_TOOL_NAME, ok=True)
_DECLINED = ToolRun(name=FORGET_CHOSEN_TOOL_NAME, ok=False)
_READ = ToolRun(name="read_text_file", ok=True)
_UNTRUSTED_GONE = ToolRun(name=FORGET_UNTRUSTED_TOOL_NAME, ok=True)


def _forget(unmatched: int = 0) -> TaintLedger:
    return TaintLedger(forget_asked=True, forget_calls=1, forget_unmatched=unmatched)


def _shown(
    taint: TaintLedger,
    runs: Sequence[ToolRun],
    query: str,
    *,
    reply: str = _REPLY,
    memory: bool = True,
) -> str:
    recaller = MemoryRecaller(InMemoryMemoryStore(), HashEmbedder(), SystemClock())
    caps = TurnCapabilities(memory=recaller if memory else None)
    parts = [reply]
    list(limit_notes(StopLedger(), runs, parts, caps=caps, taint=taint, query=query))
    return "".join(parts)


@pytest.mark.parametrize(
    ("taint", "runs", "query"),
    [
        (_forget(), (_DELETED,), _NEW_VALUE),
        (_forget(), (_DECLINED,), _NEW_VALUE),
        (_forget(), (), _NEW_VALUE),
        (TaintLedger(tainted=True), (_READ,), "Read notes.txt and remember what it says."),
        (TaintLedger(tainted=True), (_READ,), "Remember to read notes.txt."),
        (TaintLedger(tainted=True), (_UNTRUSTED_GONE,), _PLAIN),
        (TaintLedger(tainted=True, opaque=True), (), "Remember what is on my screen."),
    ],
    ids=["deleted", "declined", "unreadable", "file", "to-do", "untrusted-forget", "picture"],
)
def test_each_way_a_request_to_remember_stays_out_of_memory_shows_the_note(
    *, taint: TaintLedger, runs: tuple[ToolRun, ...], query: str
) -> None:
    assert _shown(taint, runs, query) == _REPLY + UNKEPT_CLAIM_NOTE


@pytest.mark.parametrize(
    ("taint", "runs", "query"),
    [
        (TaintLedger(), (), _PLAIN),
        (_forget(unmatched=1), (_DELETED,), _PLAIN),
        (TaintLedger(tainted=True), (_READ,), "What does notes.txt say?"),
        (_forget(), (_DELETED,), "Forget my old phone number."),
        (_forget(), (_DELETED,), "Remember my new number, and forget my old one."),
        (TaintLedger(), (), "Don't save this: my PIN is 5521."),
        (TaintLedger(), (), "Which folders can you read?"),
    ],
    ids=["stored", "unmatched", "file", "forget", "both", "not-kept", "folders"],
)
def test_a_silent_reply_shows_no_note_when_the_turn_is_stored_or_was_not_asked_to_keep(
    *, taint: TaintLedger, runs: tuple[ToolRun, ...], query: str
) -> None:
    assert _shown(taint, runs, query) == _REPLY


def test_a_turn_without_memory_shows_no_note_on_a_request_to_remember() -> None:
    assert _shown(TaintLedger(tainted=True), (_READ,), _PLAIN, memory=False) == _REPLY


def test_a_reply_saying_the_value_was_not_kept_still_shows_the_note() -> None:
    reply = "I could not save that, so please send it again."
    shown = _shown(_forget(), (_DELETED,), _NEW_VALUE, reply=reply)
    assert shown == reply + UNKEPT_CLAIM_NOTE
