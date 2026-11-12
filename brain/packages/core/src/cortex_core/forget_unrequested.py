"""Refuse the forget tool on a message that holds no word that can retract something."""

import re

from cortex_core.memory_forget_chosen import FORGET_CHOSEN_TOOL_NAME

FORGET_UNREQUESTED_MSG = (
    "REFUSED: the person's message asks to forget nothing, so this call was not run. Do not call "
    "it again in this turn, and answer the message itself."
)
# The words that can retract something in English, French, German, Spanish and Romanian, and the
# forget verbs of languages written in the same letters.
RETRACT_WORDS = (
    r"\b(?:forg[eo]t\w*|eras\w+|unlearn\w*|delet\w+|remov\w+|wip(?:e|es|ed|ing)|drop\w*|clear\w*"
    r"|purg\w+|discard\w*|scrub\w*|ditch\w*|scrap\w*|toss\w*|trash\w*|rid|lose|stop\w*|undo"
    r"|retract\w*|revok\w+|withdraw\w*|ignor\w+|disregard\w*|pretend\w*|regret\w*|mistak\w+"
    r"|accident\w*|wrong|take\s+back|replac\w+|no|not|never|none|nothing|rather|old|previous"
    r"|former|outdated|(?:dont|wont|cant|didnt|shouldnt|wouldnt)"
    r"|nuk\w+|kill\w*|destroy\w*|shred\w*|dump\w*|expung\w+|overwrit\w+|cancel\w*|scratch\w*"
    r"|strik\w+|cross\w*|thr[eo]w\w*|dispos\w+|blank\w*|reset\w*|clean\w*|updat\w+|chang\w+"
    r"|correct\w*|instead|earlier|prior|obsolete|stale|gone|nevermind|unsav\w*|unremember\w*"
    r"|unstor\w*|let\s+go|go\s+away|out\s+of\s+(?:your|memory)|used\s+to|must\s+go|remember\s+to|bin"
    r"|vergiss\w*|vergess\w*|vergeet|loesch\w*|entfern\w*|verwijder\w*|oubli\w*|effac\w+|olv[ií]d\w*"
    r"|b[oó]rr\w+|dimentic\w*|uit\w*|[șşs]terg\w*|sup{1,2}r[ií]m\w*|elim[ií]n\w*|l[oö]sch\w*"
    r"|ret[ií]r\w*|enl[eè]v\w*|qu[ií]t(?!e\b)\w+|scoa[st]\w*|scos\w*|streich\w*|gestrichen"
    r"|gel[oö]sch\w*|geloesch\w*|[șşs]ters\w*|[șşs]tear[sș]\w*|annul\w*|tilg\w*|plus|aucun\w*"
    r"|ancien\w*|plut[oô]t|faux|erreur\w*|corrig\w*|remplac\w*|statt|stattdessen|fr[üu]her\w*"
    r"|falsch\w*|fehler\w*|änder\w*|aender\w*|ge[äa]ndert|korrigier\w*|ersetz\w*|aktualisier\w*"
    r"|antigu\w*|anterior\w*|cambi\w*|equivoc\w*|incorrect\w*|reemplaz\w*|actualiz\w*"
    r"|vechi\w*|schimb\w*|corect\w*|gre[șşs]\w*|[îi]nlocu\w*|nici\w*|esque[çc]\w*|apag\w*"
    r"|exclu[aií]\w*|oblid\w*|esborr\w*|rimuov\w*|scord\w*|unut\w*|modifi\w*"
    r"|sil(?:in|iniz|mek)?)\b"
    r"|n['\u2019]t\b|\bn['\u2019-](?=\w)|\b(?:au\s+lieu|en\s+(?:vez|lugar)|[îi]n\s+loc)\b"
    r"|\bm(?:is|ets|ettre|ettez)\s+[àa]\s+jour"
    r"|\b(?:de|hors\s+de)\s+(?:ta|votre|la|ma)\s+m[ée]moire|\bdin\s+memori"
    r"|\bde\s+(?:tu|su|la|mi)\s+memoria|\baus\s+(?:deinem|ihrem|dem|meinem)\s+(?:ged[äa]chtnis|speicher)"
)
# A correction ("4862, pas 4826") or a request not to keep a fact can retract a stored one.
_NEGATIONS = (
    r"\b(?:nicht|nichts|nie|nein|kein\w*|ne|pas|jamais|jam[aá]s|rien|non|nu|nimic|niciodat\w*|nunca"
    r"|nada|ning[uú]n\w*)\b"
)
# The letters of English, French, German, Spanish and Romanian, which the word lists here read.
_READ_LETTERS = "a-zàâæçéèêëîïôœùûüÿäößẞáíñóúășşțţ"
# Wide on purpose: a message read wrongly here keeps the tool, as every turn did before this check.
_CAN_RETRACT = re.compile(
    rf"{RETRACT_WORDS}|{_NEGATIONS}|(?![{_READ_LETTERS}])[^\W\d_]", re.IGNORECASE
)
# Narrower than RETRACT_WORDS, since a reply often says "don't", "no" or "changes".
_ABOUT_FORGETTING = re.compile(
    r"\b(?:rid|unlearn\w*|no\s+longer|any\s?more|gone|take\s+back|out\s+of\s+(?:your|memory)|bin"
    r"|scrub\w*|ditch\w*|scrap\w*|toss\w*|trash\w*|expung\w+|shred\w*|unsav\w*|unremember\w*"
    r"|unstor\w*|let\s+go|retract\w*|revok\w+|withdraw\w*)\b",
    re.IGNORECASE,
)
_NAMES_FORGETTING = re.compile(
    r"\b(?:forg[eo]t|delet|eras|remov|wip(?:e|es|ed|ing)\b|clear|drop|discard|purg|vergiss|vergess"
    r"|vergeet|l[oö]sch|loesch|gel[oö]sch|geloesch|entfern|oubli|effac|olv[ií]d|b[oó]rr|uit|[șşs]ters"
    r"|[șşs]terg|sup{1,2}r[ií]m|elim[ií]n|ret[ií]r|enl[eè]v|qu[ií]t(?!e\b)\w|scoa[st]|scos|streich"
    r"|gestrichen)",
    re.IGNORECASE,
)


_LETTERS = re.compile(r"[a-z]{4,}", re.IGNORECASE)
_TYPO_OF = ("forget", "forgot", "delete", "remove", "erase", "unlearn")


def _one_typo(word: str, target: str) -> bool:
    """Whether ``word`` is ``target`` with one letter dropped, added, changed or two swapped."""
    if abs(len(word) - len(target)) > 1:
        return False
    first = next(
        (i for i, pair in enumerate(zip(word, target, strict=False)) if len(set(pair)) > 1), None
    )
    if first is None:
        return True
    rest, aim = word[first:], target[first:]
    swapped = rest[:2] == aim[1::-1] and rest[2:] == aim[2:]
    return swapped or rest[1:] in {aim, aim[1:]} or rest == aim[1:]


def _misspells_forgetting(text: str) -> bool:
    return any(_one_typo(w.lower(), t) for w in _LETTERS.findall(text) for t in _TYPO_OF)


def forget_unrequested(query: str, last_reply: str = "", earlier: str = "") -> frozenset[str]:
    """The forget tool, refused by name on a ``query`` with no word that can retract something.

    ``last_reply`` is the chat's last assistant message and ``earlier`` the message it answered.
    """
    if _CAN_RETRACT.search(query) or _misspells_forgetting(query):
        return frozenset()
    if any(
        _ABOUT_FORGETTING.search(text) or _NAMES_FORGETTING.search(text)
        for text in (last_reply, earlier)
    ):
        return frozenset()
    return frozenset({FORGET_CHOSEN_TOOL_NAME})
