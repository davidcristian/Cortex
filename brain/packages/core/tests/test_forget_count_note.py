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
from cortex_core.forget_count_note import FORGOT_COUNT_NOTE, FORGOT_COUNT_NOTES, forgot_count_note
from cortex_core.stops import StopLedger

NAMES_NO_REMOVAL = [
    "I've updated your gym locker number to 5521.",
    "I've changed your gym locker number.",
    "I've saved that.",
    "Should I forget your gym locker number?",
    "I haven't forgotten your gym locker number.",
    "Nothing was removed from my memory.",
    "OK.",
]
NAMES_REMOVAL = [
    "I've forgotten your gym locker number.",
    "I've removed that from my memory.",
    "Your gym locker number has been deleted.",
    "OK. I've forgotten your gym locker number.",
    "J'ai oublié ton numéro de casier.",
    "Ich habe die Schranknummer vergessen.",
    "He olvidado tu número de taquilla.",
    "Am uitat numărul dulapului.",
]


def _closed(reply: str, deleted: int, query: str = "Forget my gym locker number.") -> str:
    recaller = MemoryRecaller(InMemoryMemoryStore(), HashEmbedder(), SystemClock())
    parts = [reply]
    taint = TaintLedger(forget_asked=True, forget_calls=1, forget_deleted=deleted)
    runs = (ToolRun(name=FORGET_CHOSEN_TOOL_NAME, ok=True),)
    caps = TurnCapabilities(memory=recaller)
    list(limit_notes(StopLedger(), runs, parts, caps=caps, taint=taint, query=query))
    return "".join(parts)


@pytest.mark.parametrize("reply", NAMES_NO_REMOVAL)
def test_a_reply_naming_no_removal_after_a_delete_ends_with_the_count(reply: str) -> None:
    shown = _closed(reply, 2)
    assert shown.startswith(reply)
    assert shown.endswith(FORGOT_COUNT_NOTE.format(count=2))


@pytest.mark.parametrize("reply", NAMES_REMOVAL)
def test_a_reply_naming_the_removal_in_any_note_language_gets_no_count(reply: str) -> None:
    assert _closed(reply, 2) == reply


@pytest.mark.parametrize("reply", NAMES_NO_REMOVAL)
def test_a_turn_that_deleted_nothing_gets_no_count(reply: str) -> None:
    assert FORGOT_COUNT_NOTE.format(count=0) not in _closed(reply, 0)


@pytest.mark.parametrize(
    ("query", "language"),
    [
        ("Oublie mon numéro de casier.", "fr"),
        ("Vergiss meine Schranknummer.", "de"),
        ("Olvida mi número de taquilla, por favor.", "es"),
        ("Uită numărul meu de dulap.", "ro"),
    ],
)
def test_the_count_is_written_in_the_language_of_the_message(query: str, language: str) -> None:
    note = FORGOT_COUNT_NOTES[language].format(count=1)
    assert _closed("OK.", 1, query) == "OK." + note
    assert forgot_count_note(1, language) == note
