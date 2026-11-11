"""Find the rows a forget's text matches only inside a longer value, such as ``789`` in ``7890``."""

import re
from collections.abc import Iterable, Sequence

from cortex_core.memory import MemoryRecord
from cortex_core.note_language import ENGLISH, in_language

_HEAD = re.compile(r"\A[^\W_]+")
_TAIL = re.compile(r"[^\W_]+\Z")

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


def _bounded(text: str) -> re.Pattern[str] | None:
    """A search for ``text`` that no letter or digit touches at an end whose word holds a digit."""
    head, tail = _HEAD.search(text), _TAIL.search(text)
    before = head is not None and any(char.isdigit() for char in head.group())
    after = tail is not None and any(char.isdigit() for char in tail.group())
    if not before and not after:
        return None
    lead, trail = r"(?<![^\W_])" if before else "", r"(?![^\W_])" if after else ""
    return re.compile(f"{lead}{re.escape(text)}{trail}", re.IGNORECASE)


def inside(records: Sequence[MemoryRecord], text: str) -> frozenset[str]:
    """The ids of ``records`` holding ``text`` only inside a longer value, never on its own."""
    pattern = _bounded(text)
    if pattern is None:
        return frozenset()
    return frozenset(record.id for record in records if pattern.search(record.text) is None)
