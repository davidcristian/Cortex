import pytest

from cortex_core import (
    SCHEDULE_TOOL_NAME,
    TaintLedger,
    ToolRun,
    TurnCapabilities,
)
from cortex_core.closing_notes import limit_notes
from cortex_core.rounds_languages import ROUNDS_SPENT_NOTES, runs_said
from cortex_core.schedule_quoted import QUOTED_STORED_NOTES, quoted_stored_notes
from cortex_core.schedule_weekly_stored import WEEKLY_STORED_NOTES, weekly_stored_notes
from cortex_core.stops import StopLedger
from cortex_core.tool_loop import MAX_TOOL_STEPS

_STORED = ToolRun(name=SCHEDULE_TOOL_NAME, ok=True)
_FAILED = ToolRun(name="list_scheduled", ok=False)
_ENGLISH_WORDS = ("reminder", "daily", "Monday", "Wednesday", " and ", "Tools run", "succeeded")


@pytest.mark.parametrize(
    ("language", "runs", "said"),
    [
        (
            "fr",
            (_STORED, _FAILED),
            "Outils lancés : schedule_task (réussi), list_scheduled (échoué).",
        ),
        ("de", (_STORED,), "Ausgeführte Werkzeuge: schedule_task (erfolgreich)."),
        ("es", (_FAILED,), "Herramientas ejecutadas: list_scheduled (falló)."),
        ("ro", (), "Nu a rulat nicio unealtă."),
        ("fr", (), "Aucun outil n'a été lancé."),
    ],
)
def test_the_runs_sentence_is_written_in_the_language(
    *, language: str, runs: tuple[ToolRun, ...], said: str
) -> None:
    assert runs_said(runs, language) == said


@pytest.mark.parametrize("language", ["fr", "de", "es", "ro"])
def test_the_rounds_note_holds_no_english_word_through_limit_notes(language: str) -> None:
    query = {
        "fr": "Dis-moi quels rappels sont prévus cette semaine.",
        "de": "Sag mir, welche Erinnerungen diese Woche geplant sind.",
        "es": "Dime qué recordatorios tengo para esta semana, por favor.",
        "ro": "Spune-mi ce mementouri sunt programate săptămâna aceasta.",
    }[language]
    stops = StopLedger()
    stops.observe_round_limit()
    parts = ["Voici."]
    runs = (_STORED,)
    caps = TurnCapabilities()
    list(limit_notes(stops, runs, parts, caps=caps, taint=TaintLedger(), query=query))
    expected = ROUNDS_SPENT_NOTES[language].format(
        rounds=MAX_TOOL_STEPS, runs=runs_said(runs, language)
    )
    assert parts[-1] == expected
    assert not any(word in parts[-1] for word in _ENGLISH_WORDS)


@pytest.mark.parametrize(
    ("language", "daily", "time", "what"),
    [
        ("fr", True, "08:00", "Un rappel quotidien à 08:00"),
        ("de", False, "09:30", "Eine Erinnerung um 09:30"),
        ("es", True, "01:15", "un recordatorio diario a la 01:15"),
        ("es", False, "18:00", "un recordatorio a las 18:00"),
        ("ro", False, "", "Un memento"),
        ("de", True, "", "Eine tägliche Erinnerung"),
    ],
)
def test_the_quoted_note_names_the_repeat_and_time_in_the_language(
    *, language: str, daily: bool, time: str, what: str
) -> None:
    message = 'Anna a dit : "remind me every day at 8". Peux-tu noter qu\'elle aime les plantes ?'
    notes = quoted_stored_notes((_STORED,), message, daily=daily, time=time, language=language)
    assert notes == (QUOTED_STORED_NOTES[language].format(what=what),)
    assert not any(word in notes[0] for word in _ENGLISH_WORDS)


@pytest.mark.parametrize(
    ("language", "days"),
    [
        ("fr", "lundi, mercredi et vendredi"),
        ("de", "Montag, Mittwoch und Freitag"),
        ("es", "lunes, miércoles y viernes"),
        ("ro", "luni, miercuri și vineri"),
    ],
)
def test_the_weekly_note_names_the_days_in_the_language(*, language: str, days: str) -> None:
    held = (("abc", "Monday, Wednesday and Friday"), ("def", "Thursday"))
    notes = weekly_stored_notes(held, "C'est fait.", language)
    single = weekly_stored_notes((("abc", "Thursday"),), "Done.", language)[0]
    assert notes[0] == WEEKLY_STORED_NOTES[language].format(days=days)
    assert not any(word in note for note in (*notes, single) for word in _ENGLISH_WORDS)


def test_a_weekly_note_with_a_day_it_cannot_read_keeps_the_stored_words() -> None:
    notes = weekly_stored_notes((("abc", "weekday"),), "C'est fait.", "fr")
    assert notes == (WEEKLY_STORED_NOTES["fr"].format(days="weekday"),)


def test_an_english_weekly_note_keeps_its_english_days() -> None:
    notes = weekly_stored_notes((("abc", "Monday and Friday"),), "Done.")
    assert "every Monday and Friday." in notes[0]


def test_the_weekly_and_quoted_notes_follow_the_message_through_limit_notes() -> None:
    query = 'Anna a dit : "rappelle-moi chaque lundi". Peux-tu noter qu\'elle aime les plantes ?'
    taint = TaintLedger(weekly_stored=(("abc", "Monday"),), stored_time="08:00")
    parts = ["C'est fait."]
    caps = TurnCapabilities()
    list(limit_notes(StopLedger(), (_STORED,), parts, caps=caps, taint=taint, query=query))
    assert QUOTED_STORED_NOTES["fr"].format(what="Un rappel à 08:00") in parts
    assert WEEKLY_STORED_NOTES["fr"].format(days="lundi") in parts
