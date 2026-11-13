"""Find the rows a forget's text matches only inside a longer value, such as ``789`` in ``7890``."""

import re
from collections.abc import Iterable, Sequence

from cortex_core.forget_clauses import asking, clauses
from cortex_core.forget_kinds import MINUS, names, read_kinds
from cortex_core.forget_languages import FUNCTION, readings
from cortex_core.forget_unnamed import just_said, quantifies, row_words, unnamed
from cortex_core.memory import MemoryRecord
from cortex_core.memory_values import code_word, joined, value_spans
from cortex_core.note_language import ENGLISH, in_language
from cortex_core.tools import TurnStamp

_HEAD = re.compile(r"\A[^\W_]+")
_TAIL = re.compile(r"[^\W_]+\Z")
_KIND = re.compile(r"\b(?:cards?|accounts?|ibans?)\b", re.IGNORECASE)
_WORD = re.compile(r"[^\W\d_]{3,}")

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


def _grouped(record: str, text: str, query: str, read: str, *, ends: bool) -> bool:
    """Whether ``record`` holds ``text`` only in longer values of a kind ``read``, the part of
    ``query`` naming rows, does not name, as a last group too when ``ends``."""
    places = _places(record, text)
    return _KIND.search(read) is None and all(_part(record, at, query, ends=ends) for at in places)


def _read(texts: Sequence[str], text: str, query: str) -> str:
    """The part of ``query`` naming rows: less each remark when the rest names a row of ``texts``
    holding ``text`` whole, else all of it."""
    asked, kind = asking(query, text), read_kinds(query)
    whole = (row for row in texts if _whole(row, text))
    named = any(names(row_words(asked), row_words(row), kind=kind) for row in whole)
    return asked if named else query


def _content(query: str, part: str | None = None) -> set[str]:
    """The words of ``part``, by default ``query``, that can name a fact, less the function words
    of the readings of ``query``."""
    function = {word for language in readings(query) for word in FUNCTION.get(language, ())}
    return row_words(query if part is None else part) - function


def _ends(
    records: Sequence[MemoryRecord],
    text: str,
    pattern: re.Pattern[str],
    query: str,
    held: Sequence[MemoryRecord],
    chat: str | None,
) -> dict[str, bool]:
    """Whether to keep each row holding ``text`` as a last group: ``query`` asks for all rows only
    with a code word and names no word only it has beside a text holding ``text`` whole, or lacks
    ``text`` and names words, none its own; never ``just_said``'s row unless one is named."""
    kinds = any(code_word(word) for word in _WORD.findall(query))
    texts = [record.text for record in (*held, *records)]
    read = _read(texts, text, query)
    every = quantifies(query) and not kinds
    holding = [] if every else [row for row in texts if _whole(row, text)]
    beside = {word for row in holding for word in row_words(row)}
    words = row_words(read)
    named = any(names(words, row_words(row)) for row in texts)
    said = None if named or kinds else just_said(list(records), chat, held)
    unasked = bool(_content(query)) and pattern.search(query) is None
    kind = read_kinds(query)
    return {
        record.id: record.id != said
        and (
            (bool(holding) and not names(words, row_words(record.text) - beside, kind=kind))
            or (unasked and not names(words, row_words(record.text), kind=kind))
        )
        for record in records
    }


def inside(
    records: Sequence[MemoryRecord],
    text: str,
    query: str = "",
    held: Iterable[MemoryRecord] = (),
    session_id: str | None = None,
) -> frozenset[str]:
    """The ids of ``records`` holding ``text`` only inside a longer value, or, given the message
    ``query``, only as groups of a longer value it does not name. ``held`` are the rows just
    deleted and ``session_id`` the calling chat."""
    pattern, deleted = _bounded(text), tuple(held)
    if pattern is None:
        return frozenset()
    read = _read([row.text for row in (*deleted, *records)], text, query)
    ends = _ends(records, text, pattern, query, deleted, session_id) if query else {}
    return frozenset(
        record.id
        for record in records
        if pattern.search(record.text) is None
        or (bool(query) and _grouped(record.text, text, query, read, ends=ends[record.id]))
    )


def kept_rows(
    rows: Sequence[MemoryRecord],
    within: Sequence[MemoryRecord],
    text: str,
    stamp: TurnStamp,
    deleted: Sequence[MemoryRecord],
) -> list[MemoryRecord]:
    """The ``rows`` ``unnamed`` keeps beside the kept rows ``within``, and each holding ``text``
    whole when one is kept and the message holds ``text`` beside words naming no row."""
    inner = {row.id for row in within}
    every = unnamed([*rows, *within], text, stamp.query, deleted, stamp.session_id)
    kept = [row for row in every if row.id not in inner]
    pattern, words = _bounded(text), _content(stamp.query)
    unclear = (
        bool(within and words)
        and pattern is not None
        and pattern.search(stamp.query) is not None
        and all(words.isdisjoint(row_words(row.text)) for row in (*rows, *within))
    )
    ids = {row.id for row in kept}
    whole = [row for row in rows if unclear and row.id not in ids and _whole(row.text, text)]
    every = [*kept, *whole, *_unnamed_groups(rows, within, text, stamp.query)]
    every.extend(_after_minus(rows, stamp.query))
    return list({row.id: row for row in every}.values())


def _after_minus(rows: Sequence[MemoryRecord], query: str) -> list[MemoryRecord]:
    """The ``rows`` a word after a word for minus in a clause of ``query`` names, as the card of
    ``Uită codul 4242 mai puțin cel de pe card``, which may ask to keep them."""
    after: list[str] = []
    for clause in clauses(query):
        at = next((at for at, token in enumerate(clause) if token in MINUS), len(clause))
        after.extend(clause[at + 1 :])
    words = _content(query, " ".join(after))
    return [row for row in rows if names(words, row_words(row.text))]


def _in_longer(record: str, text: str) -> bool:
    """Whether ``record`` holds ``text`` and each place it does is inside a longer value."""
    places, spans = _places(record, text), value_spans(record)
    return bool(places) and all(
        any(low <= start and end <= high and (start, end) != (low, high) for low, high in spans)
        for start, end in places
    )


def _unnamed_groups(
    rows: Sequence[MemoryRecord], within: Sequence[MemoryRecord], text: str, query: str
) -> list[MemoryRecord]:
    """The ``rows`` holding ``text`` only inside a longer value, or matched by a ``text`` holding
    no digit, that no word or kind of ``query`` names, when it names another of ``rows`` or
    ``within``."""
    if quantifies(query):
        return []
    words, word = _content(query), not any(char.isdigit() for char in text)
    named = {row.id for row in (*rows, *within) if names(words, row_words(row.text))}
    return [
        row
        for row in rows
        if named and row.id not in named and (word or _in_longer(row.text, text))
    ]
