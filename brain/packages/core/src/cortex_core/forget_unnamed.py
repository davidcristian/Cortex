"""Keep the rows a forget by value reaches that the message names no word of; say what it forgot."""

import re
from collections.abc import Iterable, Mapping

from cortex_core.memory import MemoryRecord
from cortex_core.memory_values import code_word, digit_runs, whole_values

_WORD = re.compile(r"[^\W\d_]{3,}")
_REPLY = "\nAssistant: "
_COMMON = frozenset(
    _WORD.findall(
        "the and you your are for but not that this these those with from have has had was were "
        "all any can its our also what about please now just too out one user assistant forget "
        "delete remove erase memory"
    )
)

_EVERY = frozenset(
    _WORD.findall("all every everywhere everything partout tout tous toutes überall alle todas tot")
)

KEPT_LINE = "Kept, since your message names none of their words:"
KEPT_ALL = (
    "nothing was forgotten: each remembered exchange holding that value is about something the "
    "user's message does not name, so each was kept"
)


KEPT_NOTE = "\n\n(Still in memory, since your message names none of their words:"
_TURNS = 32


def kept_note(kept: Iterable[str]) -> str:
    """The note closing a reply that names the excerpts of the rows a forget kept."""
    return "\n".join([KEPT_NOTE, *(f"- {line}" for line in kept)]) + ")"


class KeptRows:
    """The excerpts of the rows each turn's forget calls kept as unnamed, by turn and row id."""

    def __init__(self) -> None:
        self._turns: dict[str, dict[str, str]] = {}

    def keep(self, turn: str, rows: Mapping[str, str]) -> None:
        """Record ``rows``, row id to excerpt, as kept in ``turn``."""
        self._turns[turn] = {**self._turns.pop(turn, {}), **rows}
        while len(self._turns) > _TURNS:
            del self._turns[next(iter(self._turns))]

    def drop(self, turn: str, ids: Iterable[str]) -> None:
        """Drop the rows of ``ids`` a call of ``turn`` deleted."""
        for row_id in ids:
            self._turns.get(turn, {}).pop(row_id, None)

    def held(self, turn: str) -> tuple[str, ...]:
        """The excerpts of the rows kept in ``turn`` that no later call deleted."""
        return tuple(self._turns.get(turn, {}).values())


def _keys(text: str) -> set[str]:
    """The values ``text`` holds, codes and years alike, by their letters and digits."""
    return {*whole_values(text), *digit_runs(text)}


def _words(text: str) -> set[str]:
    """The words of ``text`` that can name a fact: three or more letters, no common or code word."""
    words = {word.lower() for word in _WORD.findall(text)}
    return {word for word in words - _COMMON if not code_word(word)}


def _named(rows: list[MemoryRecord], words: set[str], deleted: Iterable[str]) -> bool:
    """Whether a word of ``words`` names a fact of ``rows`` or ``deleted``."""
    return any(not words.isdisjoint(_words(held)) for held in (*(r.text for r in rows), *deleted))


def _apart(rows: list[MemoryRecord], query: str, words: set[str], deleted: Iterable[str]) -> bool:
    """Whether ``query``, which holds the value, names one fact of ``rows`` or ``deleted`` apart."""
    if not _EVERY.isdisjoint(word.lower() for word in _WORD.findall(query)):
        return False
    return _named(rows, words, deleted)


def _just_said(rows: list[MemoryRecord], session_id: str | None) -> str | None:
    """The id of the newest of ``rows`` the chat ``session_id`` stored, if it stored one."""
    own = [record for record in rows if session_id is not None and record.session_id == session_id]
    return max(own, key=lambda record: record.at).id if own else None


def unnamed(
    records: Iterable[MemoryRecord],
    text: str,
    query: str,
    deleted: Iterable[str] = (),
    session_id: str | None = None,
) -> list[MemoryRecord]:
    """The ``records`` whose request holds a value of ``text`` and no word of ``query``; none when
    ``query`` holds that value and names no fact apart. The newest row ``session_id`` stored is
    kept only when ``query`` names a fact of the rows or of ``deleted``.
    """
    rows, asked, words = list(records), _keys(query), _words(query)
    values = _keys(text) - asked or _keys(text)
    if not values or not words or (values <= asked and not _apart(rows, query, words, deleted)):
        return []
    said = None if _named(rows, words, deleted) else _just_said(rows, session_id)
    return [
        record
        for record in rows
        if record.id != said
        and not values.isdisjoint(_keys(record.text.split(_REPLY, 1)[0]))
        and words.isdisjoint(_words(record.text))
    ]


def forgot(removed: int, holding: int, kept: int) -> str:
    """What a delete that left no match forgot; ``holding`` rows hold its numbers, ``kept`` kept."""
    if kept:
        return (
            f"forgot {removed} remembered exchanges; {kept} other remembered exchanges hold the "
            "same value but none of the words of the user's message, so they were kept and the "
            "value is still remembered"
        )
    if not holding:
        return (
            f"forgot {removed} remembered exchanges; no remembered exchange contains that text now"
        )
    return (
        f"forgot {removed} remembered exchanges that contain that text, but {holding} other "
        "remembered exchanges still hold a number a deleted one held, so that number is still "
        "remembered; a forget of the number itself would remove them"
    )
