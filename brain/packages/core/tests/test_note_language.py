import pytest

from cortex_core.note_language import ENGLISH, in_language, message_language


@pytest.mark.parametrize(
    "message",
    [
        "",
        "17:30",
        "Remind me to buy a pain au chocolat tomorrow.",
        "I'll meet you at the café with Jürgen.",
        "What is my swimming pool locker code?",
        "Was ist geplant?",
        "Ce am programat?",
        "Ok",
        "Merci, gracias!",
    ],
)
def test_a_message_with_no_clear_other_language_is_english(message: str) -> None:
    assert message_language(message) == ENGLISH


@pytest.mark.parametrize(
    ("message", "language"),
    [
        ("Rappelle-moi demain à 17h30 d'appeler ma sœur.", "fr"),
        ("Je n'enregistre pas les appels, mais le code de mon casier est 5819.", "fr"),
        ("Erinnere mich morgen um 9 Uhr an den Zahnarzt.", "de"),
        ("Recuérdame cada año el 12 de octubre el cumpleaños de Ana.", "es"),
        ("Recuerda que mi color favorito es el verde.", "es"),
        ("Amintește-mi mâine la ora 9 de dentist.", "ro"),
        ("Uită codul meu 7788.", "ro"),
        ("¿Cuándo?", "es"),
    ],
)
def test_a_message_in_another_language_names_it(message: str, language: str) -> None:
    assert message_language(message) == language


def test_a_note_with_no_form_in_the_language_stays_english() -> None:
    assert in_language("Note.", {"fr": "Remarque."}, "de") == "Note."


def test_a_note_with_a_form_in_the_language_uses_it() -> None:
    assert in_language("Note.", {"fr": "Remarque."}, "fr") == "Remarque."
