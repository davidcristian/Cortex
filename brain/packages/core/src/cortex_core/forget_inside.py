"""Find the rows a forget's text matches only inside a longer value, such as ``789`` in ``7890``."""

import re
from collections.abc import Iterable, Sequence

from cortex_core.forget_unnamed import just_said, row_words
from cortex_core.memory import MemoryRecord
from cortex_core.memory_values import joined, value_spans
from cortex_core.note_language import ENGLISH, in_language

_HEAD = re.compile(r"\A[^\W_]+")
_TAIL = re.compile(r"[^\W_]+\Z")
_KIND = re.compile(r"\b(?:cards?|accounts?|ibans?)\b", re.IGNORECASE)

INSIDE_LINE = "Kept, since they hold that text only inside a longer value:"
INSIDE_ALL = (
    "nothing was forgotten: each remembered exchange containing that text holds it only inside a "
    "longer value, which is a different value, so each was kept"
)
INSIDE_NOTE = (
    "\n\n(Still in memory, since the text a forget call searched for is in each only as part of a "
    "longer value:"
)
INSIDE_NOTES = {
    "fr": "\n\n(Toujours en mémoire, car le texte qu'un appel d'oubli recherchait n'y figure que "
    "dans une valeur plus longue :",
    "de": "\n\n(Noch gespeichert, weil der Text, nach dem ein Aufruf zum Vergessen suchte, darin "
    "nur als Teil eines längeren Werts steht:",
    "es": "\n\n(Todavía en memoria, porque el texto que buscaba una llamada de olvido solo aparece "
    "en cada uno como parte de un valor más largo:",
    "ro": "\n\n(Încă în memorie, pentru că textul căutat de un apel de uitare apare în fiecare "
    "doar ca parte a unei valori mai lungi:",
}


def inside_note(rows: Iterable[str], language: str = ENGLISH) -> str:
    """The note closing a reply that names the rows a forget kept for holding a longer value."""
    head = in_language(INSIDE_NOTE, INSIDE_NOTES, language)
    return "\n".join([head, *(f"- {row}" for row in rows)]) + ")"


def forgot_within(removed: int, inner: int) -> str:
    """What a delete forgot when ``inner`` rows left hold its text only inside a longer value."""
    return (
        f"forgot {removed} remembered exchanges; {inner} other remembered exchanges contain that "
        "text only inside a longer value, which is a different value, so they were kept"
    )


def _bounded(text: str) -> re.Pattern[str] | None:
    """A search for ``text`` that no letter or digit touches at an end whose word holds a digit."""
    head, tail = _HEAD.search(text), _TAIL.search(text)
    before = head is not None and any(char.isdigit() for char in head.group())
    after = tail is not None and any(char.isdigit() for char in tail.group())
    if not before and not after:
        return None
    lead, trail = r"(?<![^\W_])" if before else "", r"(?![^\W_])" if after else ""
    return re.compile(f"{lead}{re.escape(text)}{trail}", re.IGNORECASE)


def _places(record: str, text: str) -> list[tuple[int, int]]:
    """The start and end of each place ``record`` holds ``text``, with any spaces between words."""
    search = re.compile(r"\s+".join(map(re.escape, text.split())), re.IGNORECASE)
    return [found.span() for found in search.finditer(record)]


def _whole(record: str, text: str) -> bool:
    """Whether ``record`` holds ``text`` as a whole value of its own."""
    spans = value_spans(record)
    return any(place in spans for place in _places(record, text))


def _part(record: str, place: tuple[int, int], query: str, *, ends: bool) -> bool:
    """Whether ``place`` of ``record`` is in a longer value ``query`` lacks, not its last group
    unless ``ends``."""
    start, end = place
    piece = record[start:end]
    for low, high in value_spans(record):
        last = end == high and not record[start - 1].isalnum() and joined(piece) == piece.lower()
        named = joined(record[low:high]) in joined(query)
        within = low <= start and end <= high and place != (low, high)
        if within and (ends or not last) and not named:
            return True
    return False


def _grouped(record: str, text: str, query: str, beside: Sequence[str]) -> bool:
    """Whether ``record`` holds ``text`` only in longer values of a kind ``query`` does not name,
    as a last group too when ``beside`` holds it whole and ``query`` names no word only it has."""
    own = row_words(record) - {word for other in beside for word in row_words(other)}
    ends = bool(beside) and row_words(query).isdisjoint(own)
    places = _places(record, text)
    return _KIND.search(query) is None and all(_part(record, at, query, ends=ends) for at in places)


def _sides(
    records: Sequence[MemoryRecord], text: str, query: str, held: Iterable[str], chat: str | None
) -> dict[str, list[str]]:
    """The texts holding ``text`` whole beside each row, none for the newest row ``chat`` stored
    when ``query`` names no word of any row, since that row is what the person just said."""
    texts = (*held, *(record.text for record in records))
    beside = [row for row in texts if _whole(row, text)]
    words = row_words(query)
    named = any(not words.isdisjoint(row_words(record.text)) for record in records)
    said = None if named else just_said(list(records), chat)
    return {record.id: [] if record.id == said else beside for record in records}


def inside(
    records: Sequence[MemoryRecord],
    text: str,
    query: str = "",
    held: Iterable[str] = (),
    session_id: str | None = None,
) -> frozenset[str]:
    """The ids of ``records`` holding ``text`` only inside a longer value, never on its own, or,
    given the message ``query``, only as groups of a longer value it does not name. ``held`` are
    the texts of rows just deleted and ``session_id`` the calling chat, read as in ``_sides``."""
    pattern = _bounded(text)
    if pattern is None:
        return frozenset()
    sides = _sides(records, text, query, held, session_id) if query else {}
    return frozenset(
        record.id
        for record in records
        if pattern.search(record.text) is None
        or (bool(query) and _grouped(record.text, text, query, sides[record.id]))
    )
