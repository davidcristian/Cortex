"""Read a reply in French, German, Spanish or Romanian that says a reminder repeats every year."""

import re

from cortex_core.memory_claim_other import stated

_YEARLY = re.compile(
    r"(?<!\w)(?:chaque\s+ann[ée]e|tous\s+les\s+ans|une\s+fois\s+par\s+an|annuel\w*"
    r"|jedes\s+jahr|j[äa]hrlich\w*|einmal\s+im\s+jahr|alle\s+jahre"
    r"|cada\s+a[ñn]o|todos\s+los\s+a[ñn]os|una\s+vez\s+al\s+a[ñn]o|anual\w*"
    r"|[îi]n\s+fiecare\s+an|o\s+dat[ăa]\s+pe\s+an|an\s+de\s+an)(?!\w)",
    re.IGNORECASE,
)
# French "mes" is "my" and Romanian "luni" is also Monday, so neither counts as a month.
_MONTHLY = re.compile(
    r"(?<!\w)(?:mois|mensuel\w*|monat\w*|monatlich\w*|meses|(?:cada|al|del)\s+mes|mensual\w*"
    r"|lun[ăa]|lunii|lunar\w*)(?!\w)",
    re.IGNORECASE,
)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


def claims_yearly_other(reply: str) -> bool:
    """Whether ``reply`` says in one of four other languages that a reminder repeats every year."""
    if _MONTHLY.search(reply):
        return False
    return any(
        stated(sentence, found)
        for sentence in _SENTENCE_END.split(reply)
        if not sentence.rstrip().endswith("?")
        for found in _YEARLY.finditer(sentence)
    )
