"""Split a request to remember a new value from the request to forget the old one it holds."""

import re

from cortex_core.memory_request import REMEMBER

# The verbs `asks_to_forget` and `asks_not_kept` read as asking memory to let something go.
_VERB = r"(?:forget|erase|unlearn|delete|remove|wipe|drop|clear|purge|get\s+rid\s+of)\b"
_OPENING = r"(?:^\W*|[,;:]\s*|(?<=[.!?])\s+|\b(?:and|but|then|so|plus)\s+)"
_LEAD = r"(?:(?:please|also|just|then|now|kindly)\s+)*(?:(?:can|could|would|will)\s+you\s+)?"
RETRACTION = re.compile(rf"{_OPENING}{_LEAD}(?:please\s+)?{_VERB}", re.IGNORECASE)
_ANY_VERB = re.compile(
    rf"(?<!\bdon't\s)(?<!\bdon\u2019t\s)(?<!\bnever\s)(?<!\bnot\s)\b{_VERB}", re.IGNORECASE
)
_CLAUSE_END = re.compile(r"[,;:]|[.!?](?:\s|$)")
_CONNECTOR = re.compile(r"^\W*(?:(?:and|but|then|so|plus)\s+)*", re.IGNORECASE)
_EDGE = " \t\n,;:.!?"
_NO_FACT = re.compile(r"(?:\W*\b(?:that|this|these|those|it|down)\b)*", re.IGNORECASE)


def words_to_keep(query: str) -> str | None:
    """The words of ``query`` before its first retraction, or after it when the retraction is first.

    None when no retraction opens a clause, or the words hold a forget verb or only a request.
    """
    first = RETRACTION.search(query)
    if first is None:
        return None
    kept = query[: first.start()]
    if not kept.strip(_EDGE):
        kept = _after(query, first.end())
    kept = kept.strip(_EDGE)
    if not kept or _ANY_VERB.search(kept) or not _holds_fact(kept):
        return None
    return kept


def _holds_fact(kept: str) -> bool:
    """Whether ``kept`` holds a word past the request to remember that opens it."""
    request = REMEMBER.match(kept)
    return request is None or _NO_FACT.fullmatch(kept, request.end()) is None


def _after(query: str, start: int) -> str:
    """The words after the retraction ending at ``start``, up to the next retraction."""
    stops = [len(query)]
    request = REMEMBER.search(query, start)
    if request is not None:
        stops.append(request.start())
    end = _CLAUSE_END.search(query, start)
    if end is not None:
        stops.append(end.end())
    rest = query[min(stops) :]
    later = RETRACTION.search(rest)
    return _CONNECTOR.sub("", rest if later is None else rest[: later.start()])
