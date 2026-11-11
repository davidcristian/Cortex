from dataclasses import dataclass

import pytest

from cortex_core import (
    FORGET_CHOSEN_TOOL_NAME,
    SCHEDULE_TOOL_NAME,
    DecodeStop,
    HashEmbedder,
    InMemoryMemoryStore,
    MemoryRecaller,
    StopReason,
    SystemClock,
    TaintLedger,
    ToolRun,
    TurnCapabilities,
)
from cortex_core.access_claim import UNSEARCHED_FILES_NOTE, UNSEARCHED_FILES_NOTES
from cortex_core.chat_only_claim import KEPT_BEYOND_CHAT_NOTE, KEPT_BEYOND_CHAT_NOTES
from cortex_core.closing_notes import limit_notes
from cortex_core.file_claim import UNREAD_FOLDERS_NOTE, UNREAD_FOLDERS_NOTES
from cortex_core.forget_claim import UNFORGOTTEN_CLAIM_NOTE, UNFORGOTTEN_CLAIM_NOTES
from cortex_core.forget_unfound_claim import (
    DELETED_UNFOUND_NOTE,
    DELETED_UNFOUND_NOTES,
    UNMATCHED_FORGET_NOTE,
    UNMATCHED_FORGET_NOTES,
)
from cortex_core.memory_claim import UNKEPT_CLAIM_NOTE, UNKEPT_CLAIM_NOTES
from cortex_core.repeat_watch import REPEATED_LINE_NOTE, REPEATED_LINE_NOTES
from cortex_core.schedule_claim import (
    MONTHLY_STORED_NOTE,
    MONTHLY_STORED_NOTES,
    UNSCHEDULED_CLAIM_NOTE,
    UNSCHEDULED_CLAIM_NOTES,
)
from cortex_core.schedule_weekly import ONCE_STORED_NOTE, ONCE_STORED_NOTES
from cortex_core.stops import StopLedger
from cortex_core.turn_output import REPLY_CAPPED_NOTE, REPLY_CAPPED_NOTES


@dataclass(frozen=True)
class _Case:
    english: str
    others: dict[str, str]
    reply: str
    runs: tuple[ToolRun, ...]
    taint: TaintLedger
    memory: bool = False
    stop: str = ""


_STORED = ToolRun(name=SCHEDULE_TOOL_NAME, ok=True)
_FORGOT = ToolRun(name=FORGET_CHOSEN_TOOL_NAME, ok=True)
_ASKS = {
    "fr": "Qu'y a-t-il dans notes.txt ? Merci beaucoup pour votre aide.",
    "de": "Was ist in notes.txt? Ich danke dir, das ist sehr nett.",
    "es": "¿Qué hay en notes.txt? Muchas gracias por tu ayuda.",
    "ro": "Ce este în notes.txt? Mulțumesc mult pentru ajutor.",
    "en": "What is in notes.txt? Thanks a lot for your help.",
}
_SAYS = {
    "fr": "Merci beaucoup pour votre aide, c'est très gentil.",
    "de": "Ich danke dir, das ist sehr nett von dir.",
    "es": "Muchas gracias por tu ayuda, eres muy amable.",
    "ro": "Mulțumesc mult pentru ajutor, ești foarte amabil.",
    "en": "Thanks a lot for your help, that is very kind.",
}
_CASES = {
    "capped": _Case(
        REPLY_CAPPED_NOTE, REPLY_CAPPED_NOTES, "Half an", (), TaintLedger(), stop="capped"
    ),
    "repeated": _Case(
        REPEATED_LINE_NOTE, REPEATED_LINE_NOTES, "A line", (), TaintLedger(), stop="repeated"
    ),
    "once": _Case(
        ONCE_STORED_NOTE, ONCE_STORED_NOTES, "OK.", (_STORED,), TaintLedger(once_after_weekly=True)
    ),
    "monthly": _Case(
        MONTHLY_STORED_NOTE,
        MONTHLY_STORED_NOTES,
        "OK. I've set a reminder for you every year on March 19th.",
        (_STORED,),
        TaintLedger(monthly_stored=True),
    ),
    "unscheduled": _Case(
        UNSCHEDULED_CLAIM_NOTE,
        UNSCHEDULED_CLAIM_NOTES,
        "OK. I've set a reminder for you every year on March 19th.",
        (),
        TaintLedger(),
    ),
    "unkept": _Case(
        UNKEPT_CLAIM_NOTE,
        UNKEPT_CLAIM_NOTES,
        "I will keep this in mind for our conversation.",
        (_FORGOT,),
        TaintLedger(forget_asked=True, forget_calls=1),
        memory=True,
    ),
    "beyond-chat": _Case(
        KEPT_BEYOND_CHAT_NOTE,
        KEPT_BEYOND_CHAT_NOTES,
        "I will keep this in mind for our conversation.",
        (),
        TaintLedger(),
        memory=True,
    ),
    "unforgotten": _Case(
        UNFORGOTTEN_CLAIM_NOTE,
        UNFORGOTTEN_CLAIM_NOTES,
        "I've forgotten your code.",
        (),
        TaintLedger(),
    ),
    "unfound": _Case(
        DELETED_UNFOUND_NOTE,
        DELETED_UNFOUND_NOTES,
        "I didn't find any record of your passport number in my memory.",
        (_FORGOT, _FORGOT),
        TaintLedger(forget_asked=True, forget_calls=2, forget_unmatched=1),
    ),
    "unmatched": _Case(
        UNMATCHED_FORGET_NOTE,
        UNMATCHED_FORGET_NOTES,
        "OK.",
        (_FORGOT,),
        TaintLedger(forget_asked=True, forget_calls=1, forget_unmatched=1),
        memory=True,
    ),
    "unread": _Case(
        UNREAD_FOLDERS_NOTE,
        UNREAD_FOLDERS_NOTES,
        "I can see these folders: Documents, Photos.",
        (),
        TaintLedger(),
    ),
    "unsearched": _Case(
        UNSEARCHED_FILES_NOTE,
        UNSEARCHED_FILES_NOTES,
        "I'm sorry, but I don't have access to your files.",
        (),
        TaintLedger(sidecar_refused=True),
    ),
}


def _closed(case: str, query: str) -> str:
    shape = _CASES[case]
    recaller = MemoryRecaller(InMemoryMemoryStore(), HashEmbedder(), SystemClock())
    caps = TurnCapabilities(memory=recaller if shape.memory else None)
    parts = [shape.reply]
    taint = shape.taint
    stops = StopLedger()
    if shape.stop == "capped":
        stops.observe(DecodeStop(StopReason.CAPPED))
    if shape.stop == "repeated":
        stops.observe_repeat()
    list(limit_notes(stops, shape.runs, parts, caps=caps, taint=taint, query=query))
    return "".join(parts)


@pytest.mark.parametrize("language", ["fr", "de", "es", "ro", "en"])
@pytest.mark.parametrize("case", list(_CASES))
def test_each_claim_note_is_written_in_the_language_of_the_message(
    *, case: str, language: str
) -> None:
    shape = _CASES[case]
    english, others, reply = shape.english, shape.others, shape.reply
    note = english if language == "en" else others[language]
    query = (_ASKS if case == "unread" else _SAYS)[language]
    assert _closed(case, query) == reply + note


@pytest.mark.parametrize("case", list(_CASES))
def test_a_message_in_a_language_with_no_wording_gets_the_english_note(case: str) -> None:
    shape = _CASES[case]
    english, reply = shape.english, shape.reply
    query = "Che cosa c'è in notes.txt?" if case == "unread" else "Grazie mille, sei gentile."
    assert _closed(case, query) == reply + english


@pytest.mark.parametrize("case", list(_CASES))
def test_each_translated_note_has_four_languages_and_the_shape_of_the_english_one(
    case: str,
) -> None:
    shape = _CASES[case]
    english, others = shape.english, shape.others
    assert set(others) == {"fr", "de", "es", "ro"}
    for note in others.values():
        assert note.startswith("\n\n(")
        assert note.endswith(".)")
        assert note != english
