import pytest

from cortex_core import StopLedger, TaintLedger, TurnCapabilities
from cortex_core.closing_notes import limit_notes
from cortex_core.schedule_first_fire import (
    FIRST_FIRE_NOTE,
    FIRST_FIRE_NOTES,
    day_word,
    early_first_fire_notes,
)

_HELD = (("abc", "2026-11-12T09:00", 2),)


@pytest.mark.parametrize(
    ("query", "language", "expected"),
    [
        (
            "Souviens-toi que le code de mon casier est 4417 et rappelle-moi demain à 9h.",
            "fr",
            "\n\n(Un rappel créé ou modifié ici se déclenche pour la première fois dans 2 jours, "
            "jeudi 2026-11-12 à 09:00. Demandez à modifier son premier jour si vous pensiez à un "
            "jour ultérieur.)",
        ),
        (
            "Erinnere mich jeden Tag um 9 Uhr an das Auto, ab Freitag bitte.",
            "de",
            "\n\n(Eine hier erstellte oder geänderte Erinnerung meldet sich zum ersten Mal in 2 "
            "Tagen, Donnerstag, 2026-11-12 um 09:00. Bitten Sie um eine Änderung des ersten "
            "Tages, wenn Sie einen späteren meinten.)",
        ),
        (
            "Recuérdame cada día a las 9 mover el coche, desde el viernes por favor.",
            "es",
            "\n\n(Un recordatorio creado o cambiado aquí suena por primera vez dentro de 2 días, "
            "el jueves 2026-11-12 a las 09:00. Pide cambiar su primer día si te referías a uno "
            "posterior.)",
        ),
        (
            "Amintește-mi în fiecare zi la ora 9 de mașină, de vineri te rog.",
            "ro",
            "\n\n(Un memento creat sau modificat aici sună prima dată peste 2 zile, joi, "
            "2026-11-12 la ora 09:00. Cere să-i fie schimbată prima zi dacă te gândeai la una mai "
            "târzie.)",
        ),
        (
            "Remind me every day at 9 to move the car, from Friday.",
            "en",
            "\n\n(A reminder set or changed in this turn first fires in 2 days, Thursday "
            "2026-11-12 at 09:00. Ask to change its first day if you meant a later one.)",
        ),
    ],
)
def test_the_note_is_written_in_the_language_of_the_message(
    *, query: str, language: str, expected: str
) -> None:
    parts = ["OK."]
    taint = TaintLedger(early_first_fire=_HELD)
    list(limit_notes(StopLedger(), (), parts, caps=TurnCapabilities(), taint=taint, query=query))
    assert parts == ["OK.", expected]
    assert early_first_fire_notes(_HELD, language) == (expected,)


@pytest.mark.parametrize(
    ("language", "words"),
    [
        ("en", ("today", "tomorrow", "in 3 days")),
        ("fr", ("aujourd'hui", "demain", "dans 3 jours")),
        ("de", ("heute", "morgen", "in 3 Tagen")),
        ("es", ("hoy", "mañana", "dentro de 3 días")),
        ("ro", ("azi", "mâine", "peste 3 zile")),
        ("it", ("today", "tomorrow", "in 3 days")),
    ],
)
def test_each_day_count_has_its_words_and_another_language_reads_english(
    *, language: str, words: tuple[str, str, str]
) -> None:
    assert (day_word(0, language), day_word(1, language), day_word(3, language)) == words


def test_a_language_without_a_note_shows_the_english_note() -> None:
    expected = FIRST_FIRE_NOTE.format(
        when="tomorrow", day="Wednesday", date="2026-11-11", time="09:00"
    )
    assert early_first_fire_notes((("abc", "2026-11-11T09:00", 1),), "it") == (expected,)


def test_the_spanish_note_names_one_o_clock_with_la() -> None:
    (one,) = early_first_fire_notes((("abc", "2026-11-10T01:30", 0),), "es")
    (nine,) = early_first_fire_notes((("abc", "2026-11-10T09:00", 0),), "es")
    assert "hoy, el martes 2026-11-10 a la 01:30." in one
    assert "a las 09:00." in nine


def test_every_translated_note_names_each_field_of_the_english_one() -> None:
    for note in FIRST_FIRE_NOTES.values():
        for field in ("{when}", "{day}", "{date}", "{time}"):
            assert field in note
        assert note.startswith("\n\n(")
        assert note.endswith(".)")
