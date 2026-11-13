"""Keep the rows a forget by value reaches that the message names no word of; say what it forgot."""

import re
from collections.abc import Iterable, Mapping

from cortex_core.forget_clauses import EVERY, EXCEPT, FORGET, KEEP, clauses, parts
from cortex_core.forget_kinds import names, read_kinds
from cortex_core.forget_languages import FUNCTION, readings
from cortex_core.memory import MemoryRecord
from cortex_core.memory_values import code_stem, code_word, digit_runs, kind_word, whole_values
from cortex_core.note_language import ENGLISH, in_language, message_language

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
_TOPIC = frozenset({"about", "else", "sur", "über", "sobre"})
_REST = EVERY | frozenset({"rest", "reste", "others"})
KEPT_LINE = "Kept, since your message names none of their words or asks to keep them:"
KEPT_ALL = (
    "nothing was forgotten: each remembered exchange holding that value is about something the "
    "user's message does not name or asks to keep, so each was kept"
)
KEPT_NOTE = (
    "\n\n(Still in memory, since your message names none of their words or asks to keep them:"
)
KEPT_NOTES = {
    "fr": "\n\n(Toujours en mémoire, car votre message demande de les garder ou ne nomme aucun "
    "de leurs mots :",
    "de": "\n\n(Noch gespeichert, weil Ihre Nachricht darum bittet, sie zu behalten, oder keines "
    "ihrer Wörter nennt:",
    "es": "\n\n(Todavía en memoria, porque tu mensaje pide guardarlos o no nombra ninguna de sus "
    "palabras:",
    "ro": "\n\n(Încă în memorie, pentru că mesajul tău cere să fie păstrate sau nu numește niciun "
    "cuvânt al lor:",
}
_TURNS = 32


def kept_note(kept: Iterable[str], language: str = ENGLISH) -> str:
    """The note closing a reply that names the rows a forget kept, in the note ``language``."""
    head = in_language(KEPT_NOTE, KEPT_NOTES, language)
    return "\n".join([head, *(f"- {line}" for line in kept)]) + ")"


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

    def ids(self, turn: str) -> frozenset[str]:
        """The ids of the rows kept in ``turn`` that no later call deleted."""
        return frozenset(self._turns.get(turn, {}))

    def held(self, turn: str) -> tuple[str, ...]:
        """The excerpts of the rows kept in ``turn`` that no later call deleted."""
        return tuple(self._turns.get(turn, {}).values())


def _keys(text: str) -> set[str]:
    """The values ``text`` holds, codes and years alike, by their letters and digits."""
    return {*whole_values(text), *digit_runs(text)}


def _words(text: str, function: frozenset[str] = frozenset()) -> set[str]:
    """The words of ``text`` that can name a fact: three or more letters, no common or code word."""
    words = {word.lower() for word in _WORD.findall(text)}
    return {word for word in words - _COMMON - function - EVERY if not code_word(word)}


def _stems(text: str) -> set[str]:
    """The stems of the compound code words of ``text``, such as ``fahrrad`` of ``Fahrradcode``."""
    return {stem for word in _WORD.findall(text) if (stem := code_stem(word)) is not None}


def _kinds(text: str) -> set[str]:
    """The code words of ``text`` naming one kind of value, such as ``pin`` or ``passcode``."""
    return {word.lower() for word in _WORD.findall(text) if kind_word(word)}


def row_words(text: str) -> set[str]:
    """The words of a stored exchange that can name a fact, with the stems of its compounds."""
    plain = _PREFIX.sub("\n", text)
    return _words(plain) | _stems(plain)


def _row_names(text: str) -> set[str]:
    """The words of a stored exchange a forget part or keep clause can name it by."""
    return row_words(text) | _kinds(_PREFIX.sub("\n", text))


def _named(rows: list[MemoryRecord], words: set[str], deleted: Iterable[MemoryRecord]) -> bool:
    """Whether a word of ``words`` names a fact of ``rows`` or ``deleted``."""
    return any(names(words, row_words(record.text)) for record in (*rows, *deleted))


def _lists(text: str, listed: set[str], values: set[str], *, kind: frozenset[str]) -> bool:
    """Whether a forget part naming ``listed``, or only the whole ``values``, names the row."""
    held = whole_values(text.split(_REPLY, 1)[0])
    return names(listed, _row_names(text), kind=kind) or not values.isdisjoint(held)


def _whole(rows: list[MemoryRecord], query: str, keep: set[str], language: str) -> set[str]:
    """The whole values of a forget part naming no word, when each word of its keep clause names
    a row of ``rows``, so a keep clause read in part lists no row; else none."""
    words, kind = keep - FUNCTION.get(language, frozenset()), read_kinds(query)
    names_all = all(
        any(names({word}, _row_names(row.text), kind=kind) for row in rows) for word in words
    )
    return set(whole_values(" ".join(parts(query)[0]))) if words and names_all else set()


def _split(query: str, language: str) -> tuple[set[str], set[str], set[str] | None, bool]:
    """The words of ``query`` read in ``language`` naming a fact to forget, those only of a clause
    asking to keep, the words naming the rows to delete beside one, and whether it has a compound.
    """
    forget_tokens, keep_tokens = parts(query)
    forget, keep = " ".join(forget_tokens), " ".join(keep_tokens)
    function = FUNCTION.get(language, frozenset())
    named = _words(forget, function) | _stems(forget)
    kept = _words(keep) | _stems(keep) | _kinds(keep)
    kept = {word for word in kept - named - _kinds(forget) - EXCEPT if not KEEP.fullmatch(word)}
    listed = (named or _kinds(forget)) if keep_tokens else None
    return named, kept, listed, bool(_stems(forget))


def keep_words(query: str) -> set[str]:
    """The words naming a fact that only a clause of ``query`` asking to keep holds."""
    return _split(query, message_language(query))[1]


def asks_to_forget_keeping(query: str) -> bool:
    """Whether ``query`` names a forget verb outside a clause asking to keep that names a fact."""
    return bool(keep_words(query)) and any(FORGET.fullmatch(token) for token in parts(query)[0])


def asks_to_keep(text: str, query: str) -> bool:
    """Whether a clause of ``query`` asking to keep names a fact of the row ``text``, or all."""
    kept = keep_words(query)
    return not _REST.isdisjoint(parts(query)[1]) or not kept.isdisjoint(_row_names(text))


def quantifies(query: str) -> bool:
    """Whether a word for all in ``query`` asks for every row: within two words of a value."""
    split = clauses(query)
    for index, clause in enumerate(split):
        if any(KEEP.fullmatch(token) for token in clause):
            continue
        for at, token in enumerate(clause):
            if token not in EVERY or (at + 1 < len(clause) and clause[at + 1] in _TOPIC):
                continue
            beside = [*clause[max(0, at - 2) : at], *clause[at + 1 : at + 3]]
            if len(clause) == 1 and index:
                beside = split[index - 1][-1:]
            if any(char.isdigit() for char in "".join(beside)):
                return True
    return False


def just_said(
    rows: list[MemoryRecord], session_id: str | None, deleted: Iterable[MemoryRecord] = ()
) -> str | None:
    """The id of the newest of ``rows`` the chat ``session_id`` stored, if it stored one and no
    row it stored in ``deleted``, the rows the turn deleted, is newer."""
    held = (*rows, *deleted)
    own = [record for record in held if session_id is not None and record.session_id == session_id]
    newest = max(own, key=lambda record: record.at).id if own else None
    return newest if any(record.id == newest for record in rows) else None


def unnamed(
    records: Iterable[MemoryRecord],
    text: str,
    query: str,
    deleted: Iterable[MemoryRecord] = (),
    session_id: str | None = None,
) -> list[MemoryRecord]:
    """The ``records`` to keep, each a reading of ``query`` in one of its ``readings`` keeps."""
    rows, deleted = list(records), list(deleted)
    if not query.strip():
        return []
    kept = {
        record.id
        for language in readings(query)
        for record in _unnamed(rows, text, query, deleted, session_id, language)
    }
    return [record for record in rows if record.id in kept]


def _unnamed(
    rows: list[MemoryRecord],
    text: str,
    query: str,
    deleted: list[MemoryRecord],
    session_id: str | None,
    language: str,
) -> list[MemoryRecord]:
    """The ``rows`` to keep: with a keep clause, each no word or value outside it names or it names;
    else each whose request holds a value of ``text`` and no word of ``query``, unless it asks
    for every row, or names nothing and is the row ``just_said`` reads beside ``deleted``."""
    words, keep, listed, compound = _split(query, language)
    if listed is not None:
        # A clause asks to keep: list only a row a whole word or value names; a misread keeps it.
        values = set[str]() if listed else _whole(rows, query, keep, language)
        return [
            record
            for record in rows
            if not _lists(record.text, listed, values, kind=read_kinds(query))
            or names(keep, _row_names(record.text))
        ]
    asked, values = _keys(query), _keys(text) - _keys(query) or _keys(text)
    named = compound or _named(rows, words, deleted)
    every = values <= asked and (not named or quantifies(query))
    said = None if named else just_said(rows, session_id, deleted)
    return [
        record
        for record in rows
        if not every
        and record.id != said
        and not values.isdisjoint(_keys(record.text.split(_REPLY, 1)[0]))
        and not names(words, row_words(record.text), kind=read_kinds(query))
    ]
