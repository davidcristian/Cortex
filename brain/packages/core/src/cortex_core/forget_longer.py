"""Find the rows a forget reaches with a value the message lacks, holding its values only longer."""

from collections.abc import Iterable, Sequence

from cortex_core.forget_inside import inside
from cortex_core.memory import MemoryRecord
from cortex_core.memory_values import digit_runs, whole_values
from cortex_core.note_language import ENGLISH, in_language

LONGER_LINE = "Kept, since they hold the value the user's message names only inside a longer value:"
LONGER_NOTE = (
    "\n\n(Still in memory, since the value your message names is in each only as part of a "
    "longer value:"
)
LONGER_NOTES = {
    "fr": "\n\n(Toujours en mémoire, car la valeur que nomme votre message n'y figure que dans "
    "une valeur plus longue :",
    "de": "\n\n(Noch gespeichert, weil der Wert, den Ihre Nachricht nennt, darin nur als Teil "
    "eines längeren Werts steht:",
    "es": "\n\n(Todavía en memoria, porque el valor que nombra tu mensaje solo aparece en cada "
    "uno como parte de un valor más largo:",
    "ro": "\n\n(Încă în memorie, pentru că valoarea pe care o numește mesajul tău apare în "
    "fiecare doar ca parte a unei valori mai lungi:",
}
LONGER_ALL = (
    "nothing was forgotten: each remembered exchange containing that text holds it, or the value "
    "the user's message names, only inside a longer value, which is a different value, so each "
    "was kept"
)


def longer_note(rows: Iterable[str], language: str = ENGLISH) -> str:
    """The note closing a reply that names the rows a forget kept for holding the message's value
    only inside a longer one."""
    head = in_language(LONGER_NOTE, LONGER_NOTES, language)
    return "\n".join([head, *(f"- {row}" for row in rows)]) + ")"


def _flat(text: str) -> str:
    """``text`` in lower case with every run of white space one space."""
    return " ".join(text.lower().split())


def _values(text: str) -> dict[str, str]:
    """The values ``text`` holds, codes and years alike, by their letters and digits."""
    return {**digit_runs(text), **whole_values(text)}


def longer(records: Sequence[MemoryRecord], text: str, query: str) -> list[MemoryRecord]:
    """The ``records`` holding every value ``query`` names only inside a longer value,
    when the call's ``text`` names a value and none of them is one ``query`` names."""
    named, asked = _values(text), _values(query)
    if not named or not asked or not named.keys().isdisjoint(asked):
        return []
    held = [
        {record.id for record in records if _flat(form) in _flat(record.text)}
        & inside(records, form)
        for form in asked.values()
    ]
    ids = held[0].intersection(*held[1:])
    return [record for record in records if record.id in ids]


def beside(removed: int, far: int) -> str:
    """What a delete forgot when ``far`` rows its card kept by ``longer`` still hold its text."""
    return (
        f"forgot {removed} remembered exchanges; {far} other remembered exchanges contain that "
        "text but hold the value the user's message names only inside a longer value, so they "
        "were kept"
    )


def longer_lines(excerpts: Iterable[str]) -> list[str]:
    """The card lines naming the rows kept by ``longer``, none when it kept none."""
    rows = [f"- {excerpt}" for excerpt in excerpts]
    return [LONGER_LINE, *rows] if rows else []
