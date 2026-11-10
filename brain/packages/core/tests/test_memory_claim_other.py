import pytest

from cortex_core.memory_claim import unkept_note_due
from cortex_core.memory_claim_other import claims_kept_other

_CLAIMS = [
    "C'est noté, je retiens que le code de votre casier est 7319.",
    "D'accord, j'ai bien noté votre rappel pour appeler le plombier à 17h30.",
    "Je l'ai enregistré.",
    "Je m'en souviendrai.",
    "Noté !",
    "Notiert.",
    "Alles klar, ich habe mir deinen Code gemerkt.",
    "Das merke ich mir.",
    "Ich werde es mir merken.",
    "Das ist gespeichert.",
    "Entendido, lo recordaré.",
    "Lo he anotado.",
    "He guardado tu código.",
    "Queda anotado.",
    "Am notat codul.",
    "Bine, am reținut.",
    "Voi ține minte asta.",
    "Notat.",
    "Pas de souci, c'est noté.",
    "Kein Problem, ich habe es notiert.",
    "No hay problema, lo he anotado.",
    "Nu-ți face griji, am notat.",
]
_NEAR_MISSES = [
    "Voulez-vous que je le note ?",
    "Si vous voulez, je le noterai.",
    "Je ne l'ai pas noté.",
    "Je n'ai rien enregistré.",
    "Ce n'est pas noté.",
    "Soll ich mir das merken?",
    "Wenn du willst, merke ich mir das.",
    "Ich habe es nicht gespeichert.",
    "Ich merke mir das nicht.",
    "¿Quieres que lo anote?",
    "Si quieres, lo recordaré.",
    "No lo he anotado.",
    "No lo recordaré.",
    "Vrei să notez asta?",
    "Dacă vrei, voi ține minte.",
    "Nu am notat nimic.",
    "N-am reținut codul.",
    "Le rendez-vous noté dans votre agenda est demain.",
    "Der notierte Termin ist morgen.",
    "Ich habe den Termin für 9 Uhr eingetragen.",
    "Ich merke mir Namen schlecht.",
    "Note my code 7319.",
    "Note-le pas.",
    "Je le note ?",
    "Speichere ich das?",
    "¿Lo anoto?",
    "Rețin asta?",
]


@pytest.mark.parametrize("reply", _CLAIMS)
def test_a_claim_to_keep_in_another_language_is_read(reply: str) -> None:
    assert claims_kept_other(reply)


@pytest.mark.parametrize("reply", _NEAR_MISSES)
def test_a_question_condition_or_negation_in_another_language_claims_nothing(reply: str) -> None:
    assert not claims_kept_other(reply)


def test_a_claim_in_another_language_shows_the_note_on_a_turn_that_stores_nothing() -> None:
    assert unkept_note_due("Quelle heure est-il ?", "C'est noté.")
    assert not unkept_note_due("Quelle heure est-il ?", "Il est 9 heures.")
