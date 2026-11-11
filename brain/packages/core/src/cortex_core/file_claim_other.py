"""Read a reply in French, German, Spanish or Romanian that says it reaches a folder."""

import re

from cortex_core.file_claim import names_one, statements
from cortex_core.file_request import asks_files, asks_files_other
from cortex_core.memory_claim_other import after_condition, stated
from cortex_core.untrusted import TaintLedger

_SOME = r"(?:[\w'\u2019]+\s+){0,4}?"
_REACH = re.compile(
    r"(?<!\w)(?:j['\u2019]ai\s+(?:aussi\s+|bien\s+)?(?:acc[eè]s|la\s+permission|le\s+droit)"
    r"|je\s+(?:peux|pourrais)\s+(?:aussi\s+)?(?:lire|acc[ée]der|voir|lister|consulter|ouvrir)"
    r"|je\s+suis\s+autoris[ée]e?"
    r"|ich\s+(?:habe|hab)\s+(?:auch\s+)?(?:zugriff|zugang)|(?:habe|hab)\s+ich\s+(?:auch\s+)?"
    rf"(?:zugriff|zugang)|ich\s+kann\s+{_SOME}(?:lesen|zugreifen|sehen|auflisten|[öo]ffnen)"
    rf"|kann\s+ich\s+{_SOME}(?:lesen|zugreifen|sehen|auflisten|[öo]ffnen)"
    r"|ich\s+(?:darf|bin\s+berechtigt)|darf\s+ich"
    r"|(?:puedo|podr[íi]a)\s+(?:tambi[ée]n\s+)?(?:leer|acceder|ver|listar|abrir|consultar)"
    r"|tengo\s+(?:tambi[ée]n\s+)?(?:acceso|permiso|permitido)|estoy\s+autorizad[oa]"
    r"|pot\s+(?:s[ăa]\s+)?(?:[șş]i\s+)?(?:citi|citesc|accesa|accesez|vedea|v[ăa]d|lista|listez"
    r"|deschide|deschid)|am\s+(?:[șş]i\s+)?(?:acces|permisiunea|permisiune|dreptul)"
    r"|sunt\s+autorizat[ăa]?)(?!\w)",
    re.IGNORECASE,
)
_EXAMPLE = re.compile(
    r"(?<!\w)(?:par\s+exemple|zum\s+beispiel|z\.\s*b\.|por\s+ejemplo|p\.\s*ej\.|de\s+exemplu)",
    re.IGNORECASE,
)
_FOLDERS = re.compile(
    r"(?<!\w)(?:dossiers?|r[ée]pertoires?|fichiers?|chemins?|emplacements?|ordner|verzeichnis\w*"
    r"|dateien|datei|pfade?|speicherorte?|carpetas?|directorios?|archivos?|rutas?|ubicaciones?"
    r"|folder\w*|directoare\w*|fi[șş]ier\w*|c[ăa]i(?:le)?|loca[țţ]ii\w*)(?!\w)",
    re.IGNORECASE,
)
# A kind of file, as in "types de fichiers" or "formatos de archivo", names no folder.
_KINDS = re.compile(
    r"(?<!\w)(?:types?|formats?|extensions?|tipos|formatos|extensiones|tipuri(?:le)?|formate(?:le)?"
    r"|extensii(?:le)?)\s+(?:de\s+|d['\u2019])?\w+",
    re.IGNORECASE,
)


def _heads_folders(heading: str) -> bool:
    """Whether ``heading`` names folders, paths or files in one of four other languages."""
    return _FOLDERS.search(_KINDS.sub(" ", heading)) is not None


def _says_it_reaches(sentence: str) -> bool:
    """Whether ``sentence`` states, with no condition or negation, that a folder can be reached."""
    if sentence.rstrip().endswith("?") or _EXAMPLE.search(sentence):
        return False
    if after_condition(sentence, len(sentence)):
        return False
    return any(stated(sentence, found) for found in _REACH.finditer(sentence))


def claims_folders_other(reply: str, *, query: str) -> bool:
    """Whether a statement in ``reply`` says in another language it reaches a folder ``query``
    does not name."""
    lines = statements(reply)
    return any(
        _says_it_reaches(line) and names_one(line, lines[index + 1 :], query, heads=_heads_folders)
        for index, line in enumerate(lines)
    )


def unread_folders_claim_other(taint: TaintLedger, query: str, reply: str) -> bool:
    """Whether ``reply`` lists folders in another language on a file question no tool answered."""
    return (
        not taint.tainted
        and (asks_files(query) or asks_files_other(query))
        and claims_folders_other(reply, query=query)
    )
