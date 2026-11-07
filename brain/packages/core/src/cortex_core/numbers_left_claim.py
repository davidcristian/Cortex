"""Close a reply that says a fact was forgotten while other memories still hold its number."""

import re

from cortex_core.forget_claim import claims_forgotten, names_removal

NUMBERS_LEFT_NOTE = (
    "\n\n(Other remembered exchanges still hold a number the forgotten ones held, so that number "
    "can still be recalled in later chats. Ask to forget the number itself to remove it.)"
)

_REMOVED = re.compile(
    r"\b(?:oubli(?:é|ée|és|ées)|supprim(?:é|ée|és|ées)|effac(?:é|ée|és|ées)"
    r"|vergessen|gelöscht|entfernt|olvid(?:é|ado|ada|ados|adas)|borrad[oa]s?|eliminad[oa]s?"
    r"|uitat|șters|sters|eliminat)\b",
    re.IGNORECASE,
)
_NEGATION = re.compile(
    r"\b(?:ne|pas|rien|jamais|aucun\w*|nicht|nichts|kein\w*|nie|no|nada|nunca|nu|nimic)\b"
    r"|\bn['\u2019]",
    re.IGNORECASE,
)
_STILL_HELD = re.compile(
    r"\bstill\s+(?:be\s+)?(?:holds?|has|have|contains?|includes?|remembers?|remembered|recalled"
    r"|stored|kept|saved|held|in\s+(?:my\s+)?memory)\b",
    re.IGNORECASE,
)
_ENGLISH_NEGATION = re.compile(r"\b(?:no|nothing|none|not|never)\b|n['\u2019]t\b", re.IGNORECASE)
_CLAUSE_BREAK = re.compile(r"[,;:]")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


def _stated(pattern: re.Pattern[str], negation: re.Pattern[str], reply: str) -> bool:
    """Whether a sentence of ``reply`` asking nothing holds ``pattern`` in an unnegated clause."""
    return any(
        not sentence.rstrip().endswith("?")
        and negation.search(_CLAUSE_BREAK.split(sentence[: found.start()])[-1]) is None
        for sentence in _SENTENCE_END.split(reply)
        for found in pattern.finditer(sentence)
    )


def says_forgotten(reply: str) -> bool:
    """Whether ``reply`` says something was forgotten or removed, in any of the five languages."""
    return claims_forgotten(reply) or names_removal(reply) or _stated(_REMOVED, _NEGATION, reply)


def names_still_held(reply: str) -> bool:
    """Whether a statement in ``reply`` says something is still held or remembered."""
    return _stated(_STILL_HELD, _ENGLISH_NEGATION, reply)


def numbers_left_claim(reply: str, *, left: bool) -> bool:
    """Whether ``reply`` says a fact was forgotten that ``left`` rows still hold a number of."""
    return left and says_forgotten(reply) and not names_still_held(reply)
