import pytest

from cortex_core import TaintLedger, TurnCapabilities
from cortex_core.access_claim import (
    UNSEARCHED_FILES_NOTES,
    claims_no_access,
    claims_not_found,
    unsearched_files_claim,
)
from cortex_core.access_claim_other import claims_no_access_other, claims_not_found_other
from cortex_core.closing_notes import limit_notes
from cortex_core.stops import StopLedger

NEAR_MISSES = [
    "Est-ce que je n'ai pas accès à vos fichiers ?",
    "Si je n'ai pas accès au fichier, je vous demanderai le total.",
    "Je ne vois pas pourquoi ce serait un problème.",
    "Je ne vois pas d'inconvénient à le retenir.",
    "Je ne trouve pas que ce soit grave.",
    "J'ai accès au dossier que vous avez nommé.",
    "C'est noté, je m'en souviendrai.",
    "Habe ich keinen Zugriff auf Ihre Dateien?",
    "Wenn ich keinen Zugriff auf die Datei habe, frage ich nach der Summe.",
    "Ich sehe keinen Grund, das zu ändern.",
    "Ich finde das nicht schlimm.",
    "Ich habe Zugriff auf den Ordner, den Sie genannt haben.",
    "¿No tengo acceso a tus archivos?",
    "Si no tengo acceso al archivo, te pediré el total.",
    "No veo por qué sería un problema.",
    "No veo ningún problema en recordarlo.",
    "Tengo acceso a la carpeta que nombraste.",
    "Nu am acces la fișierele tale?",
    "Dacă nu am acces la fișier, îți voi cere totalul.",
    "Nu văd de ce ar fi o problemă.",
    "Nu văd niciun motiv să schimb asta.",
    "Am acces la folderul pe care l-ai numit.",
]

NO_ACCESS = [
    "Je n'ai pas accès à vos fichiers personnels.",
    "Je ne peux pas accéder à votre bail.",
    "Ich habe keinen Zugriff auf Ihre Dateien.",
    "Ich kann nicht auf Ihre Dateien zugreifen.",
    "No tengo acceso a tus archivos personales.",
    "No puedo acceder a tu contrato.",
    "Nu am acces la fișierele tale personale.",
    "Nu pot accesa contractul tău.",
]

NOT_FOUND = [
    "Je ne trouve pas de tableau de budget dans mes fichiers.",
    "Je n'ai trouvé aucun fichier nommé budget.",
    "Je ne vois pas ce fichier.",
    "Ich kann die Datei nicht finden.",
    "Ich finde keine Budgettabelle.",
    "Ich habe keine Datei gefunden.",
    "No encuentro ninguna hoja de presupuesto.",
    "No he encontrado el archivo.",
    "Nu găsesc foaia de buget.",
    "Nu am găsit niciun fișier cu acest nume.",
]


@pytest.mark.parametrize("reply", NEAR_MISSES)
def test_a_question_condition_or_reason_is_not_a_no_access_or_not_found_claim(reply: str) -> None:
    assert not claims_no_access_other(reply)
    assert not claims_not_found_other(reply)


@pytest.mark.parametrize("reply", NO_ACCESS)
def test_a_no_access_claim_in_another_language_is_read(reply: str) -> None:
    assert claims_no_access_other(reply)
    assert not claims_no_access(reply)


@pytest.mark.parametrize("reply", NOT_FOUND)
def test_a_not_found_claim_in_another_language_is_read(reply: str) -> None:
    assert claims_not_found_other(reply)
    assert not claims_not_found(reply)


def test_the_claim_needs_a_refused_file_call() -> None:
    assert unsearched_files_claim(TaintLedger(sidecar_refused=True), NO_ACCESS[0])
    assert unsearched_files_claim(TaintLedger(sidecar_refused=True), NOT_FOUND[0])
    assert not unsearched_files_claim(TaintLedger(), NO_ACCESS[0])


def test_a_french_no_access_claim_ends_with_the_french_note() -> None:
    parts = [NO_ACCESS[0]]
    taint = TaintLedger(sidecar_refused=True)
    query = "Retiens que le total de mon tableau de budget est 400 euros."
    caps = TurnCapabilities()
    list(limit_notes(StopLedger(), (), parts, caps=caps, taint=taint, query=query))
    assert parts[-1] == UNSEARCHED_FILES_NOTES["fr"]
