import pytest

from cortex_core import ToolRun
from cortex_core.schedule_claim import unscheduled_claim
from cortex_core.schedule_claim_other import claims_scheduled_other
from cortex_core.schedule_tools import SCHEDULE_TOOL_NAME

NEAR_MISSES = [
    "Voulez-vous que je programme un rappel ?",
    "Si vous voulez, j'ai programmé ce genre de rappel pour d'autres.",
    "Je n'ai pas programmé de rappel.",
    "Je peux programmer un rappel pour 17h30.",
    "J'ai bien noté votre adresse.",
    "Je vous rappelle que la réunion est à 17h30.",
    "Soll ich eine Erinnerung für 17:30 Uhr einstellen?",
    "Wenn du willst, ich habe die Erinnerung eingestellt.",
    "Ich habe die Erinnerung nicht eingestellt.",
    "Ich kann eine Erinnerung für 17:30 Uhr einstellen.",
    "Ich habe deine Adresse gespeichert.",
    "¿Quieres que programe un recordatorio?",
    "Cuando quieras, he programado el recordatorio.",
    "No he programado ningún recordatorio.",
    "Puedo crear un recordatorio para las 17:30.",
    "He guardado tu dirección.",
    "Vrei să programez un memento?",
    "Dacă vrei, am programat mementoul.",
    "Nu am programat niciun memento.",
    "Pot seta un memento pentru ora 17:30.",
    "Am salvat adresa ta.",
    "Ce am programat?",
    "Was ist geplant?",
    "¿Qué tengo programado?",
    "C'est fait ! Je vous rappellerai d'appeler le plombier aujourd'hui à 17h30.",
    "Ich erinnere dich morgen um 9 Uhr.",
    "Te lo recordaré mañana a las 9.",
    "Îți voi aminti mâine la ora 9.",
]
CLAIMS = [
    "D'accord, j'ai bien noté votre rappel pour appeler le plombier à 17h30.",
    "C'est fait, j'ai programmé un rappel aujourd'hui à 17h30.",
    "C'est programmé pour demain.",
    "Le rappel est réglé pour 17h30.",
    "Ich habe die Erinnerung für 17:30 Uhr eingestellt.",
    "Die Erinnerung ist jetzt gespeichert.",
    "He programado un recordatorio para las 17:30.",
    "El recordatorio queda configurado para mañana.",
    "Am programat un memento pentru astăzi la ora 17:30.",
    "Am setat mementoul pentru mâine.",
]


@pytest.mark.parametrize("reply", NEAR_MISSES)
def test_a_question_condition_negation_offer_or_promise_claims_no_schedule(reply: str) -> None:
    assert not claims_scheduled_other(reply)


@pytest.mark.parametrize("reply", CLAIMS)
def test_a_schedule_claim_in_another_language_is_read(reply: str) -> None:
    assert claims_scheduled_other(reply)
    assert unscheduled_claim((), reply)
    assert not unscheduled_claim((ToolRun(name=SCHEDULE_TOOL_NAME, ok=True),), reply)
