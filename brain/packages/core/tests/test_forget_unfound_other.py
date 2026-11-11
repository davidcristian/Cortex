import pytest

from cortex_core import FORGET_CHOSEN_TOOL_NAME, TaintLedger, ToolRun, TurnCapabilities
from cortex_core.closing_notes import limit_notes
from cortex_core.forget_unfound_claim import DELETED_UNFOUND_NOTES, unfound_claim
from cortex_core.forget_unfound_other import says_not_stored_other
from cortex_core.stops import StopLedger

_RUN = ToolRun(FORGET_CHOSEN_TOOL_NAME, ok=True)

NEAR_MISSES = [
    "Avez-vous un autre code que je n'ai pas trouvé ?",
    "Si je ne trouve pas votre code, je vous le dirai.",
    "J'ai trouvé et supprimé votre code de ma mémoire.",
    "J'ai supprimé le code, il n'est plus enregistré.",
    "J'ai supprimé le code, il n'en reste aucune trace.",
    "Votre nouveau numéro n'a pas été enregistré, envoyez-le à nouveau.",
    "Haben Sie die Nummer nicht gefunden?",
    "Wenn ich den Code nicht finde, sage ich es Ihnen.",
    "Ich habe den Code gefunden und gelöscht.",
    "Ich habe den Code gelöscht, er ist nicht mehr gespeichert.",
    "Ihre neue Nummer wurde nicht gespeichert.",
    "¿No encontraste el código?",
    "Si no encuentro tu código, te lo diré.",
    "He encontrado y borrado tu código.",
    "He borrado el código, ya no está guardado.",
    "Tu nuevo número no se guardó.",
    "Nu ai găsit codul?",
    "Dacă nu găsesc codul, îți spun.",
    "Am găsit și am șters codul.",
    "Am șters codul, nu mai este salvat.",
    "Numărul tău nou nu a fost salvat.",
    "I didn't find your code.",
    "There is no gas left in the car.",
]

NOT_STORED = [
    "J'ai supprimé votre code. Je n'ai pas trouvé votre numéro de passeport dans ma mémoire.",
    "Je n'ai trouvé aucun numéro de passeport à supprimer.",
    "Votre numéro de passeport n'a jamais été enregistré.",
    "Je n'ai aucune trace de votre numéro de passeport.",
    "Je ne trouve pas votre numéro de passeport.",
    "Ich habe Ihre Passnummer nicht gefunden.",
    "Ihre Passnummer wurde nie gespeichert.",
    "Ich habe keinen Eintrag zu Ihrer Passnummer.",
    "Zu Ihrer Passnummer ist nichts gespeichert.",
    "No encontré tu número de pasaporte en mi memoria.",
    "Tu número de pasaporte nunca se guardó.",
    "No tengo ningún registro de tu número de pasaporte.",
    "No he encontrado ningún número de pasaporte para borrar.",
    "Nu am găsit numărul tău de pașaport în memorie.",
    "N-am găsit numărul de pașaport.",
    "Numărul tău de pașaport nu a fost salvat niciodată.",
    "Nu am nicio înregistrare cu numărul tău de pașaport.",
]


@pytest.mark.parametrize("reply", NEAR_MISSES)
def test_a_question_condition_find_held_delete_or_new_fact_is_not_read(reply: str) -> None:
    assert not says_not_stored_other(reply)


@pytest.mark.parametrize("reply", NOT_STORED)
def test_a_reply_in_another_language_saying_nothing_was_found_is_read(reply: str) -> None:
    assert says_not_stored_other(reply)


def test_a_french_reply_after_a_delete_and_a_miss_ends_with_the_french_note() -> None:
    reply = NOT_STORED[0]
    parts = [reply]
    taint = TaintLedger(forget_asked=True, forget_calls=2, forget_unmatched=1)
    query = "Oublie mon code et mon numéro de passeport, merci."
    list(
        limit_notes(
            StopLedger(), (_RUN, _RUN), parts, caps=TurnCapabilities(), taint=taint, query=query
        )
    )
    assert "".join(parts) == reply + DELETED_UNFOUND_NOTES["fr"]


@pytest.mark.parametrize("reply", NEAR_MISSES[:6])
def test_a_french_near_miss_after_a_delete_and_a_miss_gets_no_note(reply: str) -> None:
    assert not unfound_claim((_RUN, _RUN), reply, unmatched=1)
