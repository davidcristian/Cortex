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
from cortex_core.escalate import ESCALATE_TOOL_NAME
from cortex_core.forget_claim import UNFORGOTTEN_CLAIM_NOTE, claims_forgotten
from cortex_core.forget_uncalled import (
    HANDED_FORGET_NOTE,
    HANDED_FORGET_NOTES,
    UNCALLED_FORGET_NOTE,
    UNCALLED_FORGET_NOTES,
    uncalled_note_due,
)
from cortex_core.forget_unnamed import asks_to_forget_keeping
from cortex_core.memory_old_value import old_value_note
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
PLAIN = (
    "Forget 7319.",
    "Forget all my codes.",
    "Forget everything.",
    "Forget it but quickly.",
    "Forget my gym code.",
    "Please forget my gym code.",
    "Can you forget my gym code?",
    "I want you to forget my gym code.",
    "Erase my gym code.",
    "Delete my gym code from your memory.",
    "Remember my card and forget the old one.",
    "Did you forget? Forget my gym code.",
    "Note that my phone number is out of date, delete it.",
    "Remember the code 7319 and wipe the PIN.",
    "Note that my phone number is now 0699000000, and delete the old one.",
)
NEAR_MISSES = (
    "Don't forget my dentist appointment.",
    "Do not forget my card.",
    "Never forget my card.",
    "Don't forget to call my mother.",
    "Keep my card.",
    "Keep my card, I will need it.",
    "Remember my card and don't forget it.",
    "I forgot my keys.",
    "Did you forget?",
    "Did you forget my card?",
    "You forgot to remind me.",
    "I always forget my gym code.",
    "Forgetting a code is common.",
    "My grandmother forgot my birthday.",
    "N'oublie pas ma carte.",
    "J'ai oublié mes clés.",
    "Vergiss es nicht.",
    "Ich habe meine Schlüssel vergessen.",
    "No olvides mi tarjeta.",
    "Olvidé mis llaves.",
    "Nu uita cardul meu.",
    "Am uitat cheile.",
    "Uită-te la asta.",
    "Delete my 9am reminder.",
    "Remove the alarm for tomorrow, and remind me at 10 instead.",
    "Remember to delete the draft.",
    "Remember that I deleted my account.",
)
# Read as a request too wide on purpose, since the note is true on every turn with no forget call.
WIDE = (
    "I forgot everything but my card.",
    "Forget all but quickly.",
    "Forget it, never mind.",
)
_OTHER = {
    "fr": "Oublie tout sauf ma carte.",
    "de": "Vergiss alles außer meiner Karte.",
    "es": "Olvida todo excepto mi tarjeta.",
    "ro": "Uită tot exceptând cardul meu.",
}
_OTHER_PLAIN = {
    "fr": "Oublie mon code de la salle de sport.",
    "de": "Vergiss meinen Code für das Fitnessstudio.",
    "es": "Olvida mi código del gimnasio.",
    "ro": "Uită codul meu de la sală.",
}
# A removal claim with the memory word before its verb, which the claim reader does not read.
_CLEARED = (
    "I have ensured that only your card number (4111 1111 1111 4242) is kept in my memory; all "
    "other information has been cleared."
)


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
def test_a_statement_read_as_a_forget_gets_the_note(query: str) -> None:
    assert _closed(query) == _ONLY + UNCALLED_FORGET_NOTE


def test_a_french_statement_read_as_a_forget_gets_the_note_in_french() -> None:
    query = "Il arrive en retard et oublie ses clés."
    assert _closed(query) == _ONLY + UNCALLED_FORGET_NOTES["fr"]


@pytest.mark.parametrize("query", PLAIN)
def test_a_forget_with_no_keep_clause_and_no_forget_call_ends_with_the_note(query: str) -> None:
    assert not asks_to_forget_keeping(query)
    assert _closed(query) == _ONLY + UNCALLED_FORGET_NOTE


@pytest.mark.parametrize("query", NEAR_MISSES)
def test_a_message_that_does_not_ask_to_forget_gets_no_note(query: str) -> None:
    assert not uncalled_note_due(query, ())
    assert _closed(query) == _ONLY


def test_a_removal_claim_the_claim_reader_misses_on_a_plain_forget_gets_the_note() -> None:
    assert not claims_forgotten(_CLEARED)
    assert _closed("Forget my gym code.", _CLEARED) == _CLEARED + UNCALLED_FORGET_NOTE


def test_the_note_that_an_old_value_is_still_held_takes_the_place_of_the_note() -> None:
    parts = ["Noted."]
    taint = TaintLedger(old_value="8426")
    query = "Remember that my new locker code is 9001, and forget the old code."
    notes = limit_notes(StopLedger(), (), parts, caps=TurnCapabilities(), taint=taint, query=query)
    list(notes)
    assert UNCALLED_FORGET_NOTE not in "".join(parts)
    assert "".join(parts) == "Noted." + old_value_note("8426", "en")


@pytest.mark.parametrize("language", list(_OTHER_PLAIN))
def test_a_plain_forget_in_another_language_gets_the_note_in_it(language: str) -> None:
    assert _closed(_OTHER_PLAIN[language]) == _ONLY + UNCALLED_FORGET_NOTES[language]


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


_HANDING = "I am handing this to the deep model, which will forget your gym code."


def test_a_reply_handing_the_forget_to_the_deep_model_gets_the_note_before_the_handoff() -> None:
    runs = (ToolRun(ESCALATE_TOOL_NAME, ok=True),)
    assert _closed("Forget my gym code.", _HANDING, runs) == _HANDING + HANDED_FORGET_NOTE


@pytest.mark.parametrize("language", list(_OTHER_PLAIN))
def test_the_note_before_a_handoff_is_written_in_the_language_of_the_message(
    language: str,
) -> None:
    runs = (ToolRun(ESCALATE_TOOL_NAME, ok=True),)
    closed = _closed(_OTHER_PLAIN[language], _HANDING, runs)
    assert closed == _HANDING + HANDED_FORGET_NOTES[language]


def test_the_note_before_a_handoff_stays_true_when_the_deep_model_never_answers() -> None:
    assert HANDED_FORGET_NOTE.endswith("before the handoff to the deep model: no forget call ran.)")


def test_a_reply_whose_handoff_was_declined_gets_the_note() -> None:
    runs = (ToolRun(ESCALATE_TOOL_NAME, ok=False),)
    assert _closed("Forget my gym code.", _HANDING, runs) == _HANDING + UNCALLED_FORGET_NOTE


def test_the_deep_model_reply_with_no_forget_call_after_a_handoff_gets_the_note() -> None:
    parts = ["I could not find it."]
    earlier = (ToolRun(ESCALATE_TOOL_NAME, ok=True),)
    caps, taint = TurnCapabilities(), TaintLedger()
    notes = limit_notes(
        StopLedger(),
        (),
        parts,
        caps=caps,
        taint=taint,
        query="Forget my gym code.",
        earlier=earlier,
    )
    list(notes)
    assert "".join(parts) == "I could not find it." + UNCALLED_FORGET_NOTE


def test_a_reply_saying_it_forgot_gets_only_the_note_that_nothing_was_forgotten() -> None:
    reply = "I've forgotten everything except your card."
    assert _closed("Forget everything but my card.", reply) == reply + UNFORGOTTEN_CLAIM_NOTE


@pytest.mark.parametrize("language", list(_OTHER))
def test_the_note_is_written_in_the_language_of_the_message(language: str) -> None:
    assert _closed(_OTHER[language]) == _ONLY + UNCALLED_FORGET_NOTES[language]


def test_the_note_says_no_forget_call_ran_so_a_refused_call_keeps_it_true() -> None:
    assert UNCALLED_FORGET_NOTE.endswith(": no forget call ran.)")


@pytest.mark.parametrize(
    ("english", "notes"),
    [(UNCALLED_FORGET_NOTE, UNCALLED_FORGET_NOTES), (HANDED_FORGET_NOTE, HANDED_FORGET_NOTES)],
)
def test_each_translated_note_has_the_shape_of_the_english_one(
    english: str, notes: dict[str, str]
) -> None:
    assert set(notes) == {"fr", "de", "es", "ro"}
    for note in notes.values():
        assert note.startswith("\n\n(")
        assert note.endswith(".)")
        assert note != english
