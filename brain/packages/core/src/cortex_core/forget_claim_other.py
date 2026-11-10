"""Read a reply in French, German, Spanish or Romanian that says something was forgotten."""

import re

from cortex_core.memory_claim_other import stated

_FR = r"\b(?:j['\u2019]ai|c['\u2019]est|(?:a|ont)\s+[ée]t[ée]|est|sont)\s+(?:bien\s+|aussi\s+)?"
_SOME_DE = r"(?:(?!(?:nicht|nie|kein\w*)\b)[\w'\u2019]+\s+){0,6}?"
_DE = rf"\b(?:ich\s+habe|ist|sind|wurde|wurden)\s+{_SOME_DE}"
_ES = r"\b(?:he|ha\s+sido|han\s+sido|queda|est[áa])\s+"
_RO = r"\b(?:am|a\s+fost|au\s+fost|e|este)\s+"
# "J'ai oublié de vous demander" says the reply forgot to do something.
_FORGOT = re.compile(
    rf"(?:{_FR}oubli[ée]e?s?|{_DE}vergessen|{_ES}olvidad[oa]s?|{_RO}uitat[ăe]?)\b"
    r"(?!\s+(?:de|d['\u2019]|zu|s[ăa])(?!\w))",
    re.IGNORECASE,
)
_DELETED = re.compile(
    rf"(?:{_FR}(?:supprim|effac)[ée]e?s?|{_DE}(?:gel[öo]scht|entfernt)"
    rf"|{_ES}(?:borrad|eliminad)[oa]s?|{_RO}(?:[șşs]ters|eliminat)[ăe]?)\b",
    re.IGNORECASE,
)
# The present counts for French only, and never after "que" ("Voulez-vous que j'oublie ce point").
_FORGETS = re.compile(
    r"(?<!que\s)\b(?:j['\u2019]|je\s+(?:l['\u2019]|les\s+))oublie\b(?!\s+(?:de|d['\u2019])(?!\w))",
    re.IGNORECASE,
)
_DELETES = re.compile(
    r"(?<!que\s)\b(?:j['\u2019]efface|je\s+(?:l['\u2019]|les\s+)?(?:supprime|efface))\b",
    re.IGNORECASE,
)
# "J'oublie souvent mes clés" tells a habit rather than a forget of this turn.
_HABIT = re.compile(
    r"(?<!\w)(?:toujours|souvent|parfois|tout\s+le\s+temps|facilement|vite|r[ée]guli[èe]rement"
    r"|chaque\s+fois|d['\u2019]habitude)(?!\w)",
    re.IGNORECASE,
)
# A deletion counts only beside memory, since a reminder or a file is deleted in the same words.
_MEMORY = re.compile(
    r"\b(?:m[ée]moire|ged[äa]chtnis|speicher|memoria|memorie[i]?)\b", re.IGNORECASE
)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


def claims_forgotten_other(reply: str) -> bool:
    """Whether a statement in ``reply`` says in one of four other languages that it forgot."""
    for sentence in _SENTENCE_END.split(reply):
        if sentence.rstrip().endswith("?"):
            continue
        if any(
            stated(sentence, found)
            for pattern in _patterns(sentence)
            for found in pattern.finditer(sentence)
        ):
            return True
    return False


def _patterns(sentence: str) -> tuple[re.Pattern[str], ...]:
    """The claim forms read in ``sentence``: a deletion beside memory, the present in no habit."""
    now = _HABIT.search(sentence) is None
    named = _MEMORY.search(sentence) is not None
    forms = ((_FORGOT, True), (_FORGETS, now), (_DELETED, named), (_DELETES, now and named))
    return tuple(pattern for pattern, read in forms if read)
