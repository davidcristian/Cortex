import pytest

from cortex_core import (
    FORGET_CHOSEN_TOOL_NAME,
    HashEmbedder,
    InMemoryMemoryStore,
    MemoryRecaller,
    SystemClock,
    TaintLedger,
    ToolRun,
    TurnCapabilities,
)
from cortex_core.closing_notes import limit_notes
from cortex_core.forget_claim import UNFORGOTTEN_CLAIM_NOTE, unforgotten_claim
from cortex_core.forget_inside import inside_note
from cortex_core.forget_longer import longer_note
from cortex_core.forget_unnamed import kept_note
from cortex_core.stops import StopLedger

_QUERY = "Forget all 4242 except the card."
_ROWS = ("User: Remember that my locker code is 4242. Assistant: Noted.",)
_KEPT_ALL = ToolRun(name=FORGET_CHOSEN_TOOL_NAME, ok=False)
_DELETED = ToolRun(name=FORGET_CHOSEN_TOOL_NAME, ok=True)

NAMES_A_REMOVAL = [
    "I have updated your memories. I've removed the locker code and phone number, but I've kept "
    "your card number.",
    "I've updated your memories and removed the locker code and phone number.",
    "The locker code is gone now.",
    "Done, the locker code and the phone number were deleted.",
]
NAMES_NO_REMOVAL = [
    "Your locker code and your phone number are still stored.",
    "Nothing was removed.",
    "I have not deleted the locker code.",
    "Should I remove the locker code?",
    "Your card number is 4111 1111 1111 4242.",
]


@pytest.mark.parametrize("reply", NAMES_A_REMOVAL)
def test_a_reply_naming_a_removal_after_calls_that_kept_every_row_claims_one(reply: str) -> None:
    assert unforgotten_claim((_KEPT_ALL,), reply, kept=True)
    assert not unforgotten_claim((_KEPT_ALL,), reply)
    assert not unforgotten_claim((_KEPT_ALL, _DELETED), reply, kept=True)


@pytest.mark.parametrize("reply", NAMES_NO_REMOVAL)
def test_a_reply_naming_no_removal_after_calls_that_kept_every_row_claims_none(reply: str) -> None:
    assert not unforgotten_claim((_KEPT_ALL,), reply, kept=True)


def _closed(reply: str, runs: tuple[ToolRun, ...], taint: TaintLedger) -> str:
    recaller = MemoryRecaller(InMemoryMemoryStore(), HashEmbedder(), SystemClock())
    parts = [reply]
    caps = TurnCapabilities(memory=recaller)
    list(limit_notes(StopLedger(), runs, parts, caps=caps, taint=taint, query=_QUERY))
    return "".join(parts)


@pytest.mark.parametrize(
    ("taint", "note"),
    [
        (TaintLedger(forget_calls=1, forget_kept=_ROWS), kept_note(_ROWS)),
        (TaintLedger(forget_calls=1, forget_inside=_ROWS), inside_note(_ROWS)),
        (TaintLedger(forget_calls=1, forget_longer=_ROWS), longer_note(_ROWS)),
    ],
)
def test_the_note_that_nothing_was_forgotten_shows_before_the_note_naming_the_kept_rows(
    taint: TaintLedger, note: str
) -> None:
    reply = NAMES_A_REMOVAL[2]
    assert _closed(reply, (_KEPT_ALL,), taint) == reply + UNFORGOTTEN_CLAIM_NOTE + note


@pytest.mark.parametrize("reply", NAMES_NO_REMOVAL)
def test_a_reply_naming_no_removal_ends_with_only_the_note_naming_the_kept_rows(
    reply: str,
) -> None:
    taint = TaintLedger(forget_calls=1, forget_kept=_ROWS)
    assert _closed(reply, (_KEPT_ALL,), taint) == reply + kept_note(_ROWS)


def test_a_turn_in_which_a_later_call_deleted_a_row_gets_no_note_that_nothing_was() -> None:
    taint = TaintLedger(forget_calls=2, forget_deleted=1, forget_kept=_ROWS)
    closed = _closed(NAMES_A_REMOVAL[1], (_KEPT_ALL, _DELETED), taint)
    assert UNFORGOTTEN_CLAIM_NOTE not in closed


def test_a_reply_naming_a_removal_with_no_row_kept_gets_no_note_from_the_kept_rows() -> None:
    closed = _closed(NAMES_A_REMOVAL[1], (_KEPT_ALL,), TaintLedger(forget_calls=1))
    assert UNFORGOTTEN_CLAIM_NOTE not in closed
