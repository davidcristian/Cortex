"""Close a reply that says a fact was forgotten while other memories still hold its number."""

import re

from cortex_core.forget_claim import claims_forgotten, names_removal

NUMBERS_LEFT_NOTE = (
    "\n\n(Other remembered exchanges still hold a number the forgotten ones held, so that number "
    "can still be recalled in later chats. Ask to forget the number itself to remove it.)"
)
NUMBERS_LEFT_NOTES = {
    "fr": "\n\n(D'autres échanges mémorisés contiennent encore un nombre que contenaient ceux qui "
    "ont été oubliés, donc ce nombre peut encore revenir dans les conversations suivantes. "
    "Demandez à oublier ce nombre lui-même pour le supprimer.)",
    "de": "\n\n(Andere gespeicherte Unterhaltungen enthalten noch eine Zahl, die auch in den "
    "vergessenen stand, daher kann diese Zahl in späteren Chats noch abgerufen werden. Bitten Sie "
    "darum, die Zahl selbst zu vergessen, um sie zu entfernen.)",
    "es": "\n\n(Otros intercambios guardados todavía contienen un número que tenían los olvidados, "
    "así que ese número aún puede recuperarse en chats posteriores. Pide que se olvide el número "
    "en sí para eliminarlo.)",
    "ro": "\n\n(Alte schimburi memorate încă conțin un număr pe care îl conțineau cele uitate, așa "
    "că acel număr poate fi încă regăsit în conversațiile următoare. Cere să fie uitat numărul "
    "însuși pentru a-l elimina.)",
}

_REMOVED = re.compile(
    r"\b(?:oubli(?:é|ée|és|ées)|supprim(?:é|ée|és|ées)|effac(?:é|ée|és|ées)"
    r"|vergessen|gelöscht|entfernt|olvid(?:é|ado|ada|ados|adas)|borrad[oa]s?|eliminad[oa]s?"
    r"|uitat[ăe]?|[șşs]terse?|[șşs]tears[ăa]|eliminată?)\b",
    re.IGNORECASE,
)
_NEGATION = re.compile(
    r"\b(?:ne|pas|rien|jamais|aucun\w*|nicht|nichts|kein\w*|nie|no|nada|nunca|nu|nimic)\b"
    r"|\bn['\u2019]",
    re.IGNORECASE,
)
_STILL_HELD = re.compile(
    r"\bstill\s+(?:be\s+)?(?:holds?|has|have|contains?|includes?|remembers?|remembered|recalled"
    r"|stored|kept|saved|held|mentions?|mentioned|appears?\s+in|in\s+(?:my\s+)?memory)\b",
    re.IGNORECASE,
)
_ENGLISH_NEGATION = re.compile(
    r"\b(?:no|nothing|none|nowhere|not|never)\b|n['\u2019]t\b", re.IGNORECASE
)
_ENGLISH_HEDGE = re.compile(
    rf"{_ENGLISH_NEGATION.pattern}|\b(?:if|should|whether|unless|in\s+case)\b", re.IGNORECASE
)
_CLAUSE_BREAK = re.compile(r"[,;:]")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")
_OTHER_MEMORY = re.compile(
    r"\b(?:another|other|autres?|andere[nmrs]?|otros?|otras?|alt[ăa]|alte|altei|altor)\s+"
    r"(?:memor(?:y|ies)|exchanges?|souvenirs?|Erinnerung(?:en)?|Eintr(?:ag|äge)|recuerdos?"
    r"|amintir[ei])\b",
    re.IGNORECASE,
)
_HOLDING = re.compile(
    r"\b(?:holds?|contains?|includes?|mentions?|appears?\s+in|contien(?:t|nent)|enthält|enthalten"
    r"|steh(?:t|en)\s+(?:noch\s+)?in|contienen?|con[țt]ine|con[țt]in)\b",
    re.IGNORECASE,
)
# "The other memories that mention 4412 are gone" names those memories by what they hold.
_RELATIVE = re.compile(
    r"\b(?:that|which|qui|que|die|der|das|welche[nrs]?|care)\s+(?:\w+\s+)?$", re.IGNORECASE
)
_DIGIT = re.compile(r"\d")
# A condition or an ability before a removal offers it rather than saying it was done.
_OFFER = re.compile(
    r"\b(?:if|whether|unless|in\s+case|can|could|may|might|would|should|si|peu[tx]|pourr\w+"
    r"|pouv\w+|wenn|falls|ob|kann|kannst|k[oö]nn\w+|pued[eoa]\w*|podr\w+|dac[ăa]|poate|pot|po[țt]i"
    r"|put(?:ea|em|e[țt]i))\b",
    re.IGNORECASE,
)
_ANY_HEDGE = re.compile(
    rf"{_ENGLISH_HEDGE.pattern}|{_NEGATION.pattern}|{_OFFER.pattern}|\bning[uú]n\w*\b",
    re.IGNORECASE,
)


def _stated(
    pattern: re.Pattern[str],
    before: re.Pattern[str],
    reply: str,
    after: re.Pattern[str] | None = None,
    offer: re.Pattern[str] | None = None,
) -> bool:
    """Whether a sentence of ``reply`` asking nothing holds ``pattern`` in a clause that has
    ``before`` nowhere before it and ``after`` nowhere after it, and ``offer`` before it nowhere."""
    return any(
        not sentence.rstrip().endswith("?")
        and before.search(_CLAUSE_BREAK.split(sentence[: found.start()])[-1]) is None
        and (after is None or after.search(_CLAUSE_BREAK.split(sentence[found.end() :])[0]) is None)
        and (offer is None or offer.search(sentence[: found.start()]) is None)
        for sentence in _SENTENCE_END.split(reply)
        for found in pattern.finditer(sentence)
    )


def says_forgotten(reply: str) -> bool:
    """Whether ``reply`` says something was forgotten or removed, in any of the five languages."""
    return (
        claims_forgotten(reply)
        or names_removal(reply, _OFFER)
        or _stated(_REMOVED, _NEGATION, reply, offer=_OFFER)
    )


def _other_holds(clause: str) -> bool:
    """Whether ``clause`` says, with no condition, negation or removal, another memory holds it."""
    holding = _HOLDING.search(clause)
    return (
        _OTHER_MEMORY.search(clause) is not None
        and holding is not None
        and _RELATIVE.search(clause[: holding.start()]) is None
        and _DIGIT.search(clause) is not None
        and _ANY_HEDGE.search(clause) is None
        and not says_forgotten(clause)
    )


def names_still_held(reply: str) -> bool:
    """Whether ``reply`` states, with no condition or negation, that something is still held."""
    return _stated(_STILL_HELD, _ENGLISH_HEDGE, reply, _ENGLISH_NEGATION) or any(
        not sentence.rstrip().endswith("?")
        and any(map(_other_holds, _CLAUSE_BREAK.split(sentence)))
        for sentence in _SENTENCE_END.split(reply)
    )


def numbers_left_claim(reply: str, *, left: bool, counted: bool = False) -> bool:
    """Whether ``reply`` or a ``counted`` note says a fact was forgotten that ``left`` rows hold."""
    return left and (counted or says_forgotten(reply)) and not names_still_held(reply)
