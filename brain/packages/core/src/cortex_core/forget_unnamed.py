"""Keep the rows a forget by value reaches that the message names no word of; say what it forgot."""

import re
from collections.abc import Iterable, Mapping

from cortex_core.memory import MemoryRecord
from cortex_core.memory_values import code_word, digit_runs, whole_values

_WORD = re.compile(r"[^\W\d_]{3,}")
_REPLY = "\nAssistant: "
_PREFIX = re.compile(r"\AUser: |\nAssistant: ")
_COMMON = frozenset(
    _WORD.findall(
        "the and you your are for but not that this these those with from have has had was were "
        "all any can its our also what about please now just too out one forget delete remove "
        "erase memory"
    )
)

_EVERY = frozenset(
    _WORD.findall("all every everywhere everything partout tout tous toutes überall alle todas")
)
_TOPIC = frozenset({"about", "else", "sur", "über", "sobre"})
_TOKEN = re.compile(r"[^\W_]+|[,;.!?:]")
_MARKS = frozenset(",;.!?:")
_KEEP = re.compile(
    r"keep\w*|kept|behalt\w*|behält|bleib\w*|garde[rz]?|conserv\w*|guard\w*|mant[eé]n\w*"
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
    return {word for word in words - _COMMON - _EVERY if not code_word(word)}


def _row_words(text: str) -> set[str]:
    """The words of a stored exchange that can name a fact, read without its speaker labels."""
    return _words(_PREFIX.sub("\n", text))


def _named(rows: list[MemoryRecord], words: set[str], deleted: Iterable[str]) -> bool:
    """Whether a word of ``words`` names a fact of ``rows`` or ``deleted``."""
    held = (*(record.text for record in rows), *deleted)
    return any(not words.isdisjoint(_row_words(text)) for text in held)


def _clauses(query: str) -> list[list[str]]:
    """The lowercase words and values of ``query``, split at each clause mark."""
    clauses: list[list[str]] = [[]]
    for token in _TOKEN.findall(query.lower()):
        if token in _MARKS:
            clauses.append([])
        else:
            clauses[-1].append(token)
    return [clause for clause in clauses if clause]


def _quantifies(query: str) -> bool:
    """Whether a word for all in ``query`` asks for every row: within two words of a value."""
    clauses = _clauses(query)
    for index, clause in enumerate(clauses):
        if any(_KEEP.fullmatch(token) for token in clause):
            continue
        for at, token in enumerate(clause):
            if token not in _EVERY or (at + 1 < len(clause) and clause[at + 1] in _TOPIC):
                continue
            beside = [*clause[max(0, at - 2) : at], *clause[at + 1 : at + 3]]
            if len(clause) == 1 and index:
                beside = clauses[index - 1][-1:]
            if any(char.isdigit() for char in "".join(beside)):
                return True
    return False


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
    ``query`` is empty or asks for every row. The newest row ``session_id`` stored is kept only
    when ``query`` names a fact of the rows or of ``deleted``.
    """
    rows, asked, words = list(records), _keys(query), _words(query)
    values = _keys(text) - asked or _keys(text)
    named = _named(rows, words, deleted)
    every = values <= asked and (not named or _quantifies(query))
    if not values or not query.strip() or every:
        return []
    said = None if named else _just_said(rows, session_id)
    return [
        record
        for record in rows
        if record.id != said
        and not values.isdisjoint(_keys(record.text.split(_REPLY, 1)[0]))
        and words.isdisjoint(_row_words(record.text))
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
