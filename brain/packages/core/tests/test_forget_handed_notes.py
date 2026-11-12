import pytest

from cortex_core import FORGET_CHOSEN_TOOL_NAME, TaintLedger, ToolRun, TurnCapabilities
from cortex_core.closing_notes import limit_notes
from cortex_core.escalate import ESCALATE_TOOL_NAME
from cortex_core.forget_claim import (
    HANDED_CLAIM_NOTE,
    HANDED_CLAIM_NOTES,
    UNFORGOTTEN_CLAIM_NOTE,
)
from cortex_core.forget_unfound_claim import (
    HANDED_UNMATCHED_NOTE,
    UNMATCHED_FORGET_NOTE,
)
from cortex_core.stops import StopLedger

_QUERY = "Forget my gym code."
_CLAIM = "I have forgotten your gym code and handed the rest to the deep model."
_HANDED = ToolRun(ESCALATE_TOOL_NAME, ok=True)
_DECLINED = ToolRun(ESCALATE_TOOL_NAME, ok=False)
_UNMATCHED = ToolRun(FORGET_CHOSEN_TOOL_NAME, ok=True)


def _closed(
    reply: str,
    runs: tuple[ToolRun, ...],
    *,
    earlier: tuple[ToolRun, ...] = (),
    unmatched: int = 0,
) -> str:
    parts = [reply]
    taint = TaintLedger(forget_calls=unmatched, forget_unmatched=unmatched)
    caps = TurnCapabilities()
    notes = limit_notes(
        StopLedger(), runs, parts, caps=caps, taint=taint, query=_QUERY, earlier=earlier
    )
    list(notes)
    return "".join(parts)


def test_a_claim_on_a_reply_that_hands_off_gets_the_note_before_the_handoff() -> None:
    assert _closed(_CLAIM, (_HANDED,)) == _CLAIM + HANDED_CLAIM_NOTE


def test_a_claim_on_a_reply_whose_handoff_was_declined_gets_the_note_for_the_turn() -> None:
    assert _closed(_CLAIM, (_DECLINED,)) == _CLAIM + UNFORGOTTEN_CLAIM_NOTE


def test_a_claim_on_the_deep_model_reply_after_a_handoff_gets_the_note_for_the_turn() -> None:
    reply = "I have forgotten your gym code."
    assert _closed(reply, (), earlier=(_HANDED,)) == reply + UNFORGOTTEN_CLAIM_NOTE


def test_an_unmatched_forget_on_a_reply_that_hands_off_gets_the_note_before_the_handoff() -> None:
    closed = _closed("OK.", (_UNMATCHED, _HANDED), unmatched=1)
    assert closed == "OK." + HANDED_UNMATCHED_NOTE


def test_an_unmatched_forget_on_a_reply_whose_handoff_was_declined_gets_the_turn_note() -> None:
    closed = _closed("OK.", (_UNMATCHED, _DECLINED), unmatched=1)
    assert closed == "OK." + UNMATCHED_FORGET_NOTE


def test_an_unmatched_forget_before_a_handoff_gives_the_deep_model_reply_the_turn_note() -> None:
    closed = _closed("OK.", (), earlier=(_UNMATCHED, _HANDED), unmatched=1)
    assert closed == "OK." + UNMATCHED_FORGET_NOTE


@pytest.mark.parametrize("note", [HANDED_CLAIM_NOTE, *HANDED_CLAIM_NOTES.values()])
def test_the_claim_note_before_a_handoff_does_not_ask_to_ask_again(note: str) -> None:
    assert ". " not in note


@pytest.mark.parametrize("note", [HANDED_CLAIM_NOTE, HANDED_UNMATCHED_NOTE])
def test_each_note_before_a_handoff_says_nothing_of_the_whole_turn(note: str) -> None:
    assert "before the handoff to the deep model" in note
    assert "turn" not in note
    assert "is still stored" not in note
