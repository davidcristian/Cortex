"""Read whether a person's message asks that something not be kept in memory."""

import re

_KEEP = r"(?:save|store|keep|remember|record|memori[sz]e|note)"
_NOT = r"(?:don['\u2019]?t|do\s+not|never)"
# The imperative position: a sentence or clause start, or a word that opens a request rather than
# following a subject ("I just forget" states a habit).
_SUBJECT = r"(?<!\bI\s)(?<!\bwe\s)(?<!\byou\s)(?<!\bthey\s)"
_OPENS = rf"(?:^\W*|[,;:]\s*|{_SUBJECT}\b(?:please|and|but|also|just|so|then|actually|kindly)\s+)"
_DONT_KEEP = re.compile(
    rf"{_OPENS}(?:please\s+)?{_NOT}\s+(?:ever\s+)?{_KEEP}\b"
    rf"|\byou\s+(?:didn['\u2019]?t|did\s+not|wouldn['\u2019]?t|would\s+not)\s+{_KEEP}\b"
    rf"|\b(?:don['\u2019]?t|do\s+not)\s+want\s+you\s+to\s+{_KEEP}\b",
    re.IGNORECASE,
)
_NOT_FOR_MEMORY = re.compile(
    r"\bnot\s+(?:for|in|into|to)\s+your\s+(?:memory|memories|notes)\b|\boff\s+the\s+record\b",
    re.IGNORECASE,
)
_FORGET = re.compile(
    rf"{_OPENS}(?:please\s+)?forget\b"
    r"|\b(?:can|could|would|will)\s+you\s+(?:please\s+)?forget\b|\byou\s+to\s+forget\b",
    re.IGNORECASE,
)
_REMOVE = re.compile(
    r"\b(?:delete|erase|remove|wipe|drop|clear|purge)\b.*"
    r"\bfrom\s+(?:your\s+(?:memory|memories|notes)|what\s+you\s+(?:know|remember))\b",
    re.IGNORECASE,
)
_REMEMBER = re.compile(
    rf"{_OPENS}(?:please\s+)?(?:remember|note\s+that|keep\s+in\s+mind|{_NOT}\s+forget)\b",
    re.IGNORECASE,
)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


def asks_not_kept(query: str) -> bool:
    """Whether a sentence of ``query`` asks not to keep something, or to forget or remove it."""
    patterns = (_DONT_KEEP, _NOT_FOR_MEMORY, _FORGET, _REMOVE)
    return any(
        pattern.search(sentence) for sentence in _SENTENCE_END.split(query) for pattern in patterns
    )


def asks_kept(query: str) -> bool:
    """Whether a sentence of ``query`` asks, in English, that something be remembered."""
    return any(_REMEMBER.search(sentence) for sentence in _SENTENCE_END.split(query))
