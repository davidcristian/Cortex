"""Read whether a person's message asks about the files or folders the file tools reach."""

import re

from cortex_core.memory_request import asks_kept

_FILE = re.compile(
    r"\b(?:files?|folders?|director(?:y|ies)|\w+\.(?:txt|md|csv|json|pdf|docx?|log|ya?ml))\b",
    re.IGNORECASE,
)
_ASK = re.compile(
    r"\b(?:list|show|tell|read|open|find|search|look|check|give|name|which|what|where)\b|\?",
    re.IGNORECASE,
)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


def asks_files(query: str) -> bool:
    """Whether a sentence of ``query`` asks about files or folders, unless it asks to remember."""
    if asks_kept(query):
        return False
    return any(
        _FILE.search(sentence) is not None and _ASK.search(sentence) is not None
        for sentence in _SENTENCE_END.split(query)
    )


_FILE_OTHER = re.compile(
    r"(?<!\w)(?:fichiers?|dossiers?|r[ée]pertoires?|dateien|datei|ordnern?|verzeichnis(?:se|sen)?"
    r"|archivos?|carpetas?|directorios?|fi[șş]ier\w*|folder(?:e|ele|elor|ul|ului)"
    r"|director(?:ul|ului|ii|ae|oare\w*))(?!\w)",
    re.IGNORECASE,
)
_ASK_OTHER = re.compile(
    r"(?<!\w)(?:liste|listez|listeaz[ăa]|lista|listar|auflisten|montre\w*|affiche\w*|lis|lisez"
    r"|ouvre\w*|cherche\w*|trouve\w*|donne\w*|dis|dites|quel\w*|o[ùu]|zeig\w*|lies|[öo]ffne\w*"
    r"|such\w*|finde\w*|gib|nenn\w*|welche\w*|wo|was|muestra\w*|ense[ñn]a\w*|lee|abre|busca\w*"
    r"|encuentra\w*|dame|dime|cu[áa]l\w*|qu[ée]|d[óo]nde|arat[ăa]\w*|cite[șş]te|deschide\w*"
    r"|caut[ăa]|g[ăa]se[șş]te|d[ăa]-mi|spune-mi|care|ce|unde)(?!\w)|\?",
    re.IGNORECASE,
)


def asks_files_other(query: str) -> bool:
    """Whether a sentence of ``query`` asks in French, German, Spanish or Romanian about files."""
    if asks_kept(query):
        return False
    return any(
        _FILE_OTHER.search(sentence) is not None and _ASK_OTHER.search(sentence) is not None
        for sentence in _SENTENCE_END.split(query)
    )
