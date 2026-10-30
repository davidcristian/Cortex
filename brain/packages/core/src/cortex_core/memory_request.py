"""Read whether a person's message asks that something not be kept in memory."""

import re

_KEEP = r"(?:save|store|keep|remember|record|memori[sz]e|note|write(?=(?:\s+\w+)?\s+down\b))"
_NOT = r"(?:don['\u2019]?t|do\s+not|never)"
# A request starts a clause, after any adverbs, or follows a conjunction; "I just forget" and
# "people just forget" state a habit.
_SUBJECT = r"(?<!\bI\s)(?<!\bwe\s)(?<!\byou\s)(?<!\bthey\s)"
_OPENS = (
    rf"(?:^\W*|[,;:]\s*|{_SUBJECT}\b(?:and|but|so|please|kindly)\s+)"
    r"(?:(?:please|also|just|then|actually|kindly)\s+)*"
)
_DONT_KEEP = re.compile(
    rf"{_OPENS}(?:{_NOT}|no\s+need\s+to)\s+(?:ever\s+)?{_KEEP}\b"
    r"|\byou\s+(?:didn['\u2019]?t|did\s+not|wouldn['\u2019]?t|would\s+not"
    rf"|(?:don['\u2019]?t|do\s+not)\s+(?:need|have)\s+to)\s+{_KEEP}\b"
    rf"|\b(?:don['\u2019]?t|do\s+not)\s+want\s+you\s+to\s+{_KEEP}\b",
    re.IGNORECASE,
)
_NOT_FOR_MEMORY = re.compile(
    r"\bnot\s+(?:for|in|into|to)\s+your\s+(?:memory|memories|notes)\b|\boff\s+the\s+record\b",
    re.IGNORECASE,
)
_FORGET = re.compile(
    rf"{_OPENS}forget\b"
    r"|\b(?:can|could|would|will)\s+you\s+(?:please\s+)?forget\b|\byou\s+to\s+forget\b",
    re.IGNORECASE,
)
_REMOVE = re.compile(
    r"\b(?:delete|erase|remove|wipe|drop|clear|purge)\b.*"
    r"\bfrom\s+(?:your\s+(?:memory|memories|notes)|what\s+you\s+(?:know|remember))\b",
    re.IGNORECASE,
)
_REMEMBER = re.compile(
    rf"{_OPENS}(?:remember|note\s+that|keep\s+in\s+mind|{_NOT}\s+forget)\b", re.IGNORECASE
)
_THE_MESSAGE = re.compile(
    r"\W*(?:it|this|that|these|those|them|my|mine|any|anything|everything|what)\b",
    re.IGNORECASE,
)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


def _asks_not_kept(sentence: str) -> bool:
    """Whether ``sentence`` asks not to keep, forget or remove something it does not ask kept."""
    if _NOT_FOR_MEMORY.search(sentence) or _REMOVE.search(sentence):
        return True
    remember = _REMEMBER.search(sentence)
    starts = len(sentence) if remember is None else remember.start()
    # The words after a request to remember are what to keep unless they name the message:
    # "never record calls" is a rule to keep, "don't save this" is not.
    return any(
        match.start() < starts or _THE_MESSAGE.match(sentence, match.end())
        for pattern in (_DONT_KEEP, _FORGET)
        for match in pattern.finditer(sentence)
    )


def asks_not_kept(query: str) -> bool:
    """Whether a sentence of ``query`` asks not to keep something, or to forget or remove it."""
    return any(_asks_not_kept(sentence) for sentence in _SENTENCE_END.split(query))


def asks_kept(query: str) -> bool:
    """Whether a sentence of ``query`` asks, in English, that something be remembered."""
    return any(_REMEMBER.search(sentence) for sentence in _SENTENCE_END.split(query))
