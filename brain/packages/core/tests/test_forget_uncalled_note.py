import pytest

from cortex_core import (
    FORGET_CHOSEN_TOOL_NAME,
    FORGET_UNTRUSTED_TOOL_NAME,
    SCHEDULE_TOOL_NAME,
    TaintLedger,
    ToolRun,
    TurnCapabilities,
)
from cortex_core.closing_notes import limit_notes
from cortex_core.forget_claim import UNFORGOTTEN_CLAIM_NOTE
from cortex_core.forget_uncalled import (
    UNCALLED_FORGET_NOTE,
    UNCALLED_FORGET_NOTES,
    uncalled_note_due,
)
from cortex_core.forget_unnamed import asks_to_forget_keeping
from cortex_core.stops import StopLedger

_ONLY = (
    "The card number (4111 1111 1111 4242) is the only memory currently stored, so there is "
    "nothing else to forget."
)
ASKED = (
    "Forget everything but my card.",
    "Forget all but my card.",
    "Forget them all but my card.",
    "Forget everything except my card.",
    "Delete everything except my card.",
    "Forget my codes, but keep the card.",
    "Forget the code 4242, keep the card.",
    "Remove all my codes but not my card.",
)
NEAR_MISSES = (
    "Don't forget my dentist appointment.",
    "Never forget my card.",
    "Keep my card.",
    "Keep my card, I will need it.",
    "Remember my card and don't forget it.",
    "Forget 7319.",
    "Forget all my codes.",
    "Forget everything.",
    "Forget it but quickly.",
)
# Read as a request too wide on purpose, since the note is true on every turn with no forget call.
WIDE = ("I forgot everything but my card.", "Forget all but quickly.")
_OTHER = {
    "fr": "Oublie tout sauf ma carte.",
    "de": "Vergiss alles außer meiner Karte.",
    "es": "Olvida todo excepto mi tarjeta.",
    "ro": "Uită tot exceptând cardul meu.",
}


def _closed(query: str, reply: str = _ONLY, runs: tuple[ToolRun, ...] = ()) -> str:
    parts = [reply]
    caps = TurnCapabilities()
    taint = TaintLedger()
    list(limit_notes(StopLedger(), runs, parts, caps=caps, taint=taint, query=query))
    return "".join(parts)


@pytest.mark.parametrize("query", ASKED)
def test_a_forget_keeping_a_fact_with_no_forget_call_ends_with_the_note(query: str) -> None:
    assert asks_to_forget_keeping(query)
    assert _closed(query) == _ONLY + UNCALLED_FORGET_NOTE


@pytest.mark.parametrize("query", WIDE)
def test_a_statement_read_as_a_forget_keeping_a_fact_gets_the_note(query: str) -> None:
    assert _closed(query) == _ONLY + UNCALLED_FORGET_NOTE


@pytest.mark.parametrize("query", NEAR_MISSES)
def test_a_message_not_asking_to_forget_beside_a_keep_clause_gets_no_note(query: str) -> None:
    assert not asks_to_forget_keeping(query)
    assert _closed(query) == _ONLY


@pytest.mark.parametrize("name", [FORGET_CHOSEN_TOOL_NAME, FORGET_UNTRUSTED_TOOL_NAME])
@pytest.mark.parametrize("ok", [True, False])
def test_a_turn_that_made_a_forget_call_gets_no_note(*, name: str, ok: bool) -> None:
    runs = (ToolRun(name, ok=ok),)
    assert not uncalled_note_due("Forget everything but my card.", runs)


def test_a_turn_whose_only_call_is_another_tool_still_gets_the_note() -> None:
    runs = (ToolRun(SCHEDULE_TOOL_NAME, ok=True),)
    assert uncalled_note_due("Forget everything but my card.", runs)


def test_a_forget_call_before_a_handoff_counts_as_a_call() -> None:
    parts = [_ONLY]
    earlier = (ToolRun(FORGET_CHOSEN_TOOL_NAME, ok=True),)
    caps, taint = TurnCapabilities(), TaintLedger()
    query = "Forget everything but my card."
    notes = limit_notes(
        StopLedger(), (), parts, caps=caps, taint=taint, query=query, earlier=earlier
    )
    list(notes)
    assert UNCALLED_FORGET_NOTE not in "".join(parts)


def test_a_reply_saying_it_forgot_gets_only_the_note_that_nothing_was_forgotten() -> None:
    reply = "I've forgotten everything except your card."
    assert _closed("Forget everything but my card.", reply) == reply + UNFORGOTTEN_CLAIM_NOTE


@pytest.mark.parametrize("language", list(_OTHER))
def test_the_note_is_written_in_the_language_of_the_message(language: str) -> None:
    assert _closed(_OTHER[language]) == _ONLY + UNCALLED_FORGET_NOTES[language]


def test_each_translated_note_has_the_shape_of_the_english_one() -> None:
    assert set(UNCALLED_FORGET_NOTES) == {"fr", "de", "es", "ro"}
    for note in UNCALLED_FORGET_NOTES.values():
        assert note.startswith("\n\n(")
        assert note.endswith(".)")
        assert note != UNCALLED_FORGET_NOTE
