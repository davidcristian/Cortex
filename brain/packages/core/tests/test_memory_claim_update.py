import pytest

from cortex_core import (
    FORGET_CHOSEN_TOOL_NAME,
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
from cortex_core.forget_count_note import forgot_count_note
from cortex_core.memory_claim_update import claims_updated
from cortex_core.stops import StopLedger

_CORRECTION = "My bike lock code is 4862, not 4826."
_FORGET = ToolRun(name=FORGET_CHOSEN_TOOL_NAME, ok=True)
_EDIT = ToolRun(name="write_file", ok=True)

UPDATED = [
    "OK. I've updated that.",
    "I've updated that. Your gym locker number is 5512.",
    "I have now changed it to 4862.",
    "I corrected your sister's name to Hannah.",
    "I replaced 4826 with 4862.",
    "Your bike lock code has been updated.",
    "Updated! Your bike lock code is 4862.",
    "No problem, I\u2019ve updated it.",
    "I've updated it, is that right?",
    "I've updated it to no longer include 4826.",
    "I've updated that, and I haven't changed anything else.",
]

NOT_UPDATED = [
    "",
    "I can update it if you want.",
    "If you want, I can update it.",
    "I'll update it once you confirm.",
    "Let me know the new code and I'll update it.",
    "Should I update it?",
    "Have I updated the right one?",
    "I haven't updated anything.",
    "I have not changed it.",
    "I've updated nothing.",
    "Nothing has been changed.",
    "Your code hasn't been updated.",
    "As I updated you earlier, the code is 4826.",
    "Updated?",
    "The file was updated yesterday.",
]


@pytest.mark.parametrize("reply", UPDATED)
def test_a_statement_that_a_value_was_updated_is_an_update_claim(reply: str) -> None:
    assert claims_updated(reply)


@pytest.mark.parametrize("reply", NOT_UPDATED)
def test_an_offer_question_negation_or_condition_is_not_an_update_claim(reply: str) -> None:
    assert not claims_updated(reply)


def _shown(taint: TaintLedger, runs: tuple[ToolRun, ...], reply: str) -> str:
    recaller = MemoryRecaller(InMemoryMemoryStore(), HashEmbedder(), SystemClock())
    parts = [reply]
    caps = TurnCapabilities(memory=recaller)
    list(limit_notes(StopLedger(), runs, parts, caps=caps, taint=taint, query=_CORRECTION))
    return "".join(parts)


def _forgot(*, deleted: int = 0, unmatched: int = 0) -> TaintLedger:
    return TaintLedger(
        forget_asked=True, forget_calls=1, forget_deleted=deleted, forget_unmatched=unmatched
    )


def test_an_update_claim_after_a_forget_that_deleted_the_old_row_shows_the_note() -> None:
    reply = "OK. I've updated that."
    shown = _shown(_forgot(deleted=1), (_FORGET,), reply)
    assert shown == reply + UNKEPT_CLAIM_NOTE + forgot_count_note(1, "en")


def test_an_update_claim_after_a_forget_that_matched_nothing_shows_the_note() -> None:
    reply = "I've updated that."
    assert UNKEPT_CLAIM_NOTE in _shown(_forgot(unmatched=1), (_FORGET,), reply)


@pytest.mark.parametrize("reply", ["I can update it if you want.", "Should I update it?"])
def test_an_offer_or_question_after_a_forget_shows_no_unkept_note(reply: str) -> None:
    assert UNKEPT_CLAIM_NOTE not in _shown(_forgot(deleted=1), (_FORGET,), reply)


def test_an_update_claim_on_a_turn_with_no_forget_call_shows_no_note() -> None:
    reply = "I've updated that."
    assert _shown(TaintLedger(tainted=True), (_EDIT,), reply) == reply
