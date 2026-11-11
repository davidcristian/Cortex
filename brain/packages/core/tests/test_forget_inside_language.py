import pytest

from cortex_core import StopLedger, TaintLedger, TurnCapabilities
from cortex_core.closing_notes import limit_notes
from cortex_core.forget_inside import INSIDE_NOTE, INSIDE_NOTES, inside_note
from cortex_core.forget_longer import LONGER_NOTE, LONGER_NOTES, longer_note


@pytest.mark.parametrize(
    ("query", "language"),
    [
        ("Oublie 789, merci.", "fr"),
        ("Vergiss bitte 789.", "de"),
        ("Olvida 789, por favor.", "es"),
        ("Uită 789, te rog.", "ro"),
        ("Forget 789, please.", "en"),
        ("Dimentica 789.", "en"),
    ],
)
def test_the_inside_note_is_written_in_the_language_of_the_message(
    *, query: str, language: str
) -> None:
    parts = ["OK."]
    taint = TaintLedger(forget_inside=("a row",))
    list(limit_notes(StopLedger(), (), parts, caps=TurnCapabilities(), taint=taint, query=query))
    head = INSIDE_NOTE if language == "en" else INSIDE_NOTES[language]
    assert "".join(parts) == f"OK.{head}\n- a row)"
    assert inside_note(("a row",), language) == f"{head}\n- a row)"


@pytest.mark.parametrize(
    ("language", "opening"),
    [
        ("fr", "(Toujours en mémoire, car"),
        ("de", "(Noch gespeichert, weil"),
        ("es", "(Todavía en memoria, porque"),
        ("ro", "(Încă în memorie, pentru că"),
    ],
)
def test_each_translated_note_opens_as_the_kept_note_and_ends_before_the_list(
    *, language: str, opening: str
) -> None:
    note = INSIDE_NOTES[language]
    assert note.removeprefix("\n\n").startswith(opening)
    assert note.endswith(":")


@pytest.mark.parametrize(
    ("query", "language"),
    [
        ("Oublie 789, merci.", "fr"),
        ("Vergiss bitte 789.", "de"),
        ("Olvida 789, por favor.", "es"),
        ("Uită 789, te rog.", "ro"),
        ("Forget 789, please.", "en"),
    ],
)
def test_the_longer_note_is_written_in_the_language_of_the_message(
    *, query: str, language: str
) -> None:
    parts = ["OK."]
    taint = TaintLedger(forget_longer=("a row",))
    list(limit_notes(StopLedger(), (), parts, caps=TurnCapabilities(), taint=taint, query=query))
    head = LONGER_NOTE if language == "en" else LONGER_NOTES[language]
    assert "".join(parts) == f"OK.{head}\n- a row)"
    assert longer_note(("a row",), language) == f"{head}\n- a row)"


@pytest.mark.parametrize("language", ["fr", "de", "es", "ro"])
def test_each_translated_longer_note_opens_as_the_inside_note_does(*, language: str) -> None:
    opening = INSIDE_NOTES[language].removeprefix("\n\n").split(",")[0]
    assert LONGER_NOTES[language].removeprefix("\n\n").startswith(opening)
    assert LONGER_NOTES[language].endswith(":")
