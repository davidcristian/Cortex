"""Read a reply that says a fact was updated, changed, corrected or replaced."""

import re

_UPDATE = re.compile(
    r"(?<!\bas\s)\bI(?:\s+have|['\u2019]ve)?\s+(?:(?:now|just|also|already)\s+)?"
    r"(?:updated|changed|corrected|replaced|amended)\b"
    r"|\b(?:has|have)\s+(?:now\s+|already\s+)?been\s+(?:updated|changed|corrected|replaced)\b",
    re.IGNORECASE,
)
_OPENING = re.compile(
    r"^\W*(?:(?:ok(?:ay)?|done|got\s+it|sure)\W+)?updated\b(?!\s*\?)", re.IGNORECASE
)
_NEGATION = re.compile(r"\b(?:not|never|nothing)\b|n['\u2019]t\b", re.IGNORECASE)
_CLAUSE_END = re.compile(r"[,;:]|\b(?:and|but|so)\b", re.IGNORECASE)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


def claims_updated(reply: str) -> bool:
    """Whether a clause of ``reply`` that asks nothing says a value was updated."""
    if _OPENING.search(reply.lstrip().partition("\n")[0]):
        return True
    return any(
        _stated(sentence, match)
        for sentence in _SENTENCE_END.split(reply)
        for match in _UPDATE.finditer(sentence)
    )


def _stated(sentence: str, match: re.Match[str]) -> bool:
    """Whether the clause of ``sentence`` holding ``match`` is no question and has no negation."""
    starts = [found.end() for found in _CLAUSE_END.finditer(sentence, 0, match.start())]
    after = _CLAUSE_END.search(sentence, match.end())
    if after is None and sentence.rstrip().endswith("?"):
        return False
    end = len(sentence) if after is None else after.start()
    return _NEGATION.search(sentence, starts[-1] if starts else 0, end) is None
