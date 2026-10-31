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
# After any other word an adverb opens a request only when the message follows the verb:
# "use it once then forget it" asks, "my kids then forget their homework" states a habit.
_LOOSE = rf"{_SUBJECT}\b(?:also|just|then|actually)\s+"
_MESSAGE = r"\W*(?:it|this|that|these|those|them|my|mine|any|anything|everything|what)\b"
_NOT_TO_KEEP = rf"\s+(?:(?:not|never)\s+to|to\s+(?:not|never))\s+(?:ever\s+)?{_KEEP}\b"
_DONT_KEEP = re.compile(
    rf"{_OPENS}(?:{_NOT}|no\s+need\s+to)\s+(?:ever\s+)?{_KEEP}\b"
    rf"|{_LOOSE}{_NOT}\s+(?:ever\s+)?{_KEEP}\b(?={_MESSAGE})|{_OPENS}remember{_NOT_TO_KEEP}"
    r"|\byou\s+(?:didn['\u2019]?t|did\s+not|wouldn['\u2019]?t|would\s+not"
    rf"|(?:don['\u2019]?t|do\s+not)\s+(?:need|have)\s+to)\s+{_KEEP}\b"
    rf"|\b(?:don['\u2019]?t|do\s+not)\s+want\s+you\s+to\s+{_KEEP}\b",
    re.IGNORECASE,
)
_NOT_FOR_MEMORY = re.compile(
    r"\bnot\s+(?:for|in|into|to)\s+your\s+(?:memory|memories|notes)\b|\boff\s+the\s+record\b",
    re.IGNORECASE,
)
_FORGET_VERB = r"(?:forget|erase|unlearn)"
_FORGET = re.compile(
    rf"{_OPENS}{_FORGET_VERB}\b|{_LOOSE}{_FORGET_VERB}\b(?={_MESSAGE})"
    rf"|\b(?:can|could|would|will)\s+you\s+(?:please\s+)?{_FORGET_VERB}\b"
    rf"|\byou\s+to\s+{_FORGET_VERB}\b"
    rf"|{_OPENS}(?:remember\s+(?:that\s+)?)?you\s+(?:should|must|need\s+to|have\s+to)\s+"
    rf"{_FORGET_VERB}\b(?={_MESSAGE})",
    re.IGNORECASE,
)
# "drop it" must end its clause, since "drop it off at the post office" asks nothing of memory.
_DISCARD = re.compile(
    rf"(?:{_OPENS}|{_LOOSE})(?:get\s+rid\s+of\b(?={_MESSAGE})"
    rf"|stop\s+(?:remembering|saving|storing|keeping|noting)\b(?={_MESSAGE})"
    r"|drop(?=\s+(?:it|this|that|them)\s*(?:[,;.!?]|$)))",
    re.IGNORECASE,
)
_REMOVE = re.compile(
    r"\b(?:delete|erase|remove|wipe|drop|clear|purge)\b.*"
    r"\bfrom\s+(?:your\s+(?:memory|memories|notes)|what\s+you\s+(?:know|remember))\b",
    re.IGNORECASE,
)
_REMEMBER = re.compile(
    rf"{_OPENS}(?:remember(?!{_NOT_TO_KEEP}{_MESSAGE})|keep\s+in\s+mind|{_NOT}\s+forget"
    r"|note(?=\s+(?:that|this|these|those|it|my|mine|down)\b))\b",
    re.IGNORECASE,
)
_THE_MESSAGE = re.compile(_MESSAGE, re.IGNORECASE)
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
        for pattern in (_DONT_KEEP, _FORGET, _DISCARD)
        for match in pattern.finditer(sentence)
    )


def asks_not_kept(query: str) -> bool:
    """Whether a sentence of ``query`` asks not to keep something, or to forget or remove it."""
    return any(_asks_not_kept(sentence) for sentence in _SENTENCE_END.split(query))


def asks_kept(query: str) -> bool:
    """Whether a sentence of ``query`` asks, in English, that something be remembered."""
    return any(_REMEMBER.search(sentence) for sentence in _SENTENCE_END.split(query))
