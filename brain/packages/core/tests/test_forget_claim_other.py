import pytest

from cortex_core import FORGET_CHOSEN_TOOL_NAME, ToolRun
from cortex_core.forget_claim import unforgotten_claim
from cortex_core.forget_claim_other import claims_forgotten_other

NEAR_MISSES = [
    "Voulez-vous que j'oublie votre code ?",
    "Si j'ai oublié quelque chose, dites-le-moi.",
    "Je n'ai pas oublié votre code.",
    "Je peux oublier votre code si vous voulez.",
    "J'ai oublié de vous demander l'heure.",
    "J'ai supprimé le rappel de demain.",
    "Soll ich deinen Code vergessen?",
    "Wenn du willst, ich habe den Code vergessen.",
    "Ich habe deinen Code nicht vergessen.",
    "Ich kann deinen Code vergessen.",
    "Ich habe die Datei gelöscht.",
    "¿Quieres que olvide tu código?",
    "Cuando quieras, he olvidado tu código.",
    "No he olvidado tu código.",
    "Puedo borrar tu código de la memoria.",
    "He borrado el recordatorio.",
    "Vrei să uit codul?",
    "Dacă vrei, am uitat codul.",
    "Nu am uitat codul tău.",
    "Am uitat să te întreb ora.",
    "Am șters fișierul.",
    "C'est oublié ?",
    "¿He olvidado algo?",
    "Am uitat ceva?",
]
CLAIMS = [
    "J'ai oublié votre code.",
    "C'est oublié.",
    "Votre code a été supprimé de ma mémoire.",
    "Ich habe deinen Code vergessen.",
    "Der Code wurde aus dem Speicher gelöscht.",
    "He olvidado tu código.",
    "Tu código ha sido borrado de la memoria.",
    "Am uitat codul tău.",
    "Am șters codul din memorie.",
]


@pytest.mark.parametrize("reply", NEAR_MISSES)
def test_a_question_condition_negation_offer_or_other_deletion_claims_no_forget(
    reply: str,
) -> None:
    assert not claims_forgotten_other(reply)


@pytest.mark.parametrize("reply", CLAIMS)
def test_a_forget_claim_in_another_language_is_read(reply: str) -> None:
    assert claims_forgotten_other(reply)
    assert unforgotten_claim((), reply)
    assert not unforgotten_claim((ToolRun(name=FORGET_CHOSEN_TOOL_NAME, ok=True),), reply)
