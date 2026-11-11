import pytest

from cortex_core import TaintLedger, ToolRun, TurnCapabilities
from cortex_core.closing_notes import limit_notes
from cortex_core.file_claim import UNREAD_FOLDERS_NOTES, claims_folders
from cortex_core.file_claim_other import claims_folders_other, unread_folders_claim_other
from cortex_core.file_request import asks_files, asks_files_other
from cortex_core.stops import StopLedger

_ASKS = "Dis-moi quels dossiers tu peux lire sur cette machine."

NEAR_MISSES = [
    "Puis-je lire /home/user/Documents pour vous ?",
    "Si vous me donnez un chemin, par exemple /srv/data, je peux le lire.",
    "Je peux lire un dossier si vous me donnez son chemin, comme /srv/data.",
    "Je peux lire un dossier que vous nommez, par exemple /srv/data.",
    "Ich kann einen Ordner lesen, den Sie nennen, zum Beispiel /srv/data.",
    "Puedo leer una carpeta que nombres, por ejemplo /srv/data.",
    "Pot citi un folder pe care îl numești, de exemplu /srv/data.",
    "Je ne peux pas lire /home/user/Documents.",
    "Je n'ai pas accès à /home/user/Documents.",
    "Je peux lire les types de fichiers suivants :\n- .txt\n- .md",
    "Je peux lire des fichiers texte et des PDF.",
    "Kann ich /home/user/Documents für Sie lesen?",
    "Wenn Sie mir einen Pfad nennen, zum Beispiel /srv/data, kann ich ihn lesen.",
    "Ich kann /home/user/Documents nicht lesen.",
    "Ich habe keinen Zugriff auf /home/user/Documents.",
    "Ich kann die folgenden Dateiformate lesen:\n- txt\n- md",
    "¿Puedo leer /home/user/Documents por ti?",
    "Si me das una ruta, por ejemplo /srv/data, puedo leerla.",
    "No puedo leer /home/user/Documents.",
    "No tengo acceso a /home/user/Documents.",
    "Puedo leer los siguientes formatos de archivo:\n- txt\n- md",
    "Pot citi /home/user/Documents pentru tine?",
    "Dacă îmi dai o cale, de exemplu /srv/data, pot să o citesc.",
    "Nu pot citi /home/user/Documents.",
    "Nu am acces la /home/user/Documents.",
    "Pot citi următoarele tipuri de fișiere:\n- txt\n- md",
    "Je peux lire les dossiers suivants :\n```\n- /srv/data\n```",
    "La capitale de l'Australie est Canberra.",
    "I can read the following folders:\n- /srv/data",
]

CLAIMS = [
    "Je peux lire les dossiers suivants :\n- /home/user/Documents\n- /home/user/Downloads",
    "Voici les dossiers auxquels j'ai accès :\n- `home`\n- `workspace`",
    "J'ai accès à /srv/data.",
    "Ich kann die folgenden Ordner lesen:\n- /home/user/Documents",
    "Auf diese Verzeichnisse habe ich Zugriff:\n- /projects",
    "Ich habe Zugriff auf /srv/data.",
    "Puedo leer las siguientes carpetas:\n- /home/user/Documents",
    "Tengo acceso a los siguientes directorios:\n* `/projects`",
    "Puedo acceder a /srv/data.",
    "Pot citi următoarele foldere:\n- /home/user/Documents",
    "Am acces la următoarele directoare:\n- /projects",
    "Pot accesa /srv/data.",
]


@pytest.mark.parametrize("reply", NEAR_MISSES)
def test_a_question_condition_negation_or_file_kind_is_not_a_folder_claim(reply: str) -> None:
    assert not claims_folders_other(reply, query=_ASKS)


@pytest.mark.parametrize("reply", CLAIMS)
def test_a_folder_claim_in_another_language_is_read(reply: str) -> None:
    assert claims_folders_other(reply, query=_ASKS)
    assert not claims_folders(reply, query=_ASKS)


def test_a_path_the_person_typed_is_not_a_claim() -> None:
    assert not claims_folders_other("J'ai accès à /srv/data.", query="Qu'y a-t-il dans /srv/data ?")


@pytest.mark.parametrize(
    "query",
    [
        "Quels dossiers peux-tu lire ?",
        "Liste les fichiers de mon dossier Documents.",
        "Welche Ordner kannst du lesen?",
        "Zeig mir die Dateien in meinem Ordner.",
        "¿Qué carpetas puedes leer?",
        "Muestra los archivos de mi carpeta.",
        "Ce foldere poți citi?",
        "Arată-mi fișierele din dosarul meu.",
    ],
)
def test_a_file_question_in_another_language_is_read(query: str) -> None:
    assert asks_files_other(query)
    assert not asks_files(query)


@pytest.mark.parametrize(
    "query",
    [
        "Retiens que mes fichiers sont dans /srv/data.",
        "Mes fichiers sont rangés.",
        "Merk dir, dass meine Dateien in /srv liegen.",
        "Recuerda que mis archivos están en /srv.",
        "Ține minte că fișierele mele sunt în /srv.",
        "Quelle heure est-il ?",
    ],
)
def test_a_remember_request_statement_or_other_question_asks_no_files(query: str) -> None:
    assert not asks_files_other(query)


def test_the_claim_needs_a_file_question_and_a_turn_that_read_no_tool_output() -> None:
    reply = CLAIMS[0]
    assert unread_folders_claim_other(TaintLedger(), _ASKS, reply)
    assert unread_folders_claim_other(TaintLedger(), "Which folders can you read?", reply)
    assert not unread_folders_claim_other(TaintLedger(tainted=True), _ASKS, reply)
    assert not unread_folders_claim_other(TaintLedger(), "Quelle heure est-il ?", reply)


def test_a_french_folder_claim_ends_with_the_french_note() -> None:
    parts = [CLAIMS[0]]
    runs: tuple[ToolRun, ...] = ()
    caps = TurnCapabilities()
    list(limit_notes(StopLedger(), runs, parts, caps=caps, taint=TaintLedger(), query=_ASKS))
    assert parts[-1] == UNREAD_FOLDERS_NOTES["fr"]


def test_an_english_claim_under_a_french_question_ends_with_the_french_note() -> None:
    parts = ["I can read the following folders:\n- /srv/data"]
    caps = TurnCapabilities()
    list(limit_notes(StopLedger(), (), parts, caps=caps, taint=TaintLedger(), query=_ASKS))
    assert parts[-1] == UNREAD_FOLDERS_NOTES["fr"]
