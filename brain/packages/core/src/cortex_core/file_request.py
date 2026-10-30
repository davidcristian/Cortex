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
