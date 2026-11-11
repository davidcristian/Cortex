import pytest

from cortex_core import SCHEDULE_TOOL_NAME, TaintLedger, ToolRun, TurnCapabilities
from cortex_core.closing_notes import limit_notes
from cortex_core.schedule_claim import MONTHLY_STORED_NOTES
from cortex_core.schedule_yearly_other import claims_yearly_other
from cortex_core.stops import StopLedger

NEAR_MISSES = [
    "Voulez-vous qu'il se répète chaque année ?",
    "Si vous voulez qu'il revienne chaque année, dites-le-moi.",
    "Ce rappel ne se répète pas chaque année.",
    "Ce rappel revient chaque année, le 19 du mois.",
    "Mes rappels sont prêts.",
    "Soll sie sich jedes Jahr wiederholen?",
    "Wenn sie jedes Jahr kommen soll, sagen Sie es mir.",
    "Die Erinnerung wiederholt sich nicht jährlich.",
    "Die Erinnerung kommt jedes Jahr am 19. des Monats.",
    "¿Quieres que se repita cada año?",
    "Si quieres que se repita cada año, dímelo.",
    "El recordatorio no se repite cada año.",
    "El recordatorio se repite cada año, el día 19 de cada mes.",
    "Vrei să se repete în fiecare an?",
    "Dacă vrei să se repete în fiecare an, spune-mi.",
    "Mementoul nu se repetă în fiecare an.",
    "Mementoul se repetă în fiecare an, pe 19 ale lunii.",
    "I set a reminder every year.",
]

CLAIMS = [
    "J'ai créé un rappel qui se répète chaque année le 19 mars.",
    "Ce rappel reviendra tous les ans.",
    "C'est un rappel annuel pour l'anniversaire de Mes amis.",
    "Ich habe eine Erinnerung erstellt, die sich jedes Jahr am 19. März wiederholt.",
    "Die Erinnerung kommt jährlich.",
    "He creado un recordatorio que se repite cada año el 19 de marzo.",
    "Te lo recordaré todos los años.",
    "Am creat un memento care se repetă în fiecare an pe 19 martie.",
    "Îți voi aminti anual.",
]


@pytest.mark.parametrize("reply", NEAR_MISSES)
def test_a_question_condition_negation_or_month_is_not_read_as_a_yearly_claim(reply: str) -> None:
    assert not claims_yearly_other(reply)


@pytest.mark.parametrize("reply", CLAIMS)
def test_a_yearly_claim_in_another_language_is_read(reply: str) -> None:
    assert claims_yearly_other(reply)


def test_a_french_yearly_claim_over_a_monthly_rule_ends_with_the_french_note() -> None:
    reply = CLAIMS[0]
    parts = [reply]
    taint = TaintLedger(monthly_stored=True)
    runs = (ToolRun(name=SCHEDULE_TOOL_NAME, ok=True),)
    query = "Rappelle-moi chaque année le 19 mars de souhaiter son anniversaire à Paul."
    caps = TurnCapabilities()
    list(limit_notes(StopLedger(), runs, parts, caps=caps, taint=taint, query=query))
    assert "".join(parts) == reply + MONTHLY_STORED_NOTES["fr"]
