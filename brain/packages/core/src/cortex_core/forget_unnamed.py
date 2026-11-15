"""Keep the rows a forget by value reaches that the message names no word of; say what it forgot."""

import re
from collections.abc import Iterable, Mapping

from cortex_core.forget_clauses import AND, EVERY, EXCEPT, FORGET, KEEP, WHOSE, clauses, parts
from cortex_core.forget_kinds import kinds, names, read_kinds
from cortex_core.forget_languages import FUNCTION, readings
from cortex_core.memory import MemoryRecord
from cortex_core.memory_values import code_stem, code_word, digit_runs, kind_word, whole_values
from cortex_core.note_language import ENGLISH, in_language, message_language

_WORD = re.compile(r"[^\W\d_]{3,}")
_GROUP = re.compile(r"[^\W_]+")
_REPLY = "\nAssistant: "
_PREFIX = re.compile(r"\AUser: |\nAssistant: ")
_COMMON = frozenset(
    _WORD.findall(
        "the and you your are for but not that this these those with from have has had was were "
        "all any can its our also what about please now just too out one forget delete remove "
        "erase memory"
    )
)
TOPIC = frozenset({"about", "else", "sur", "über", "sobre"})
_REST = EVERY | frozenset({"rest", "reste", "others"})
KEPT_LINE = "Kept, since your message was not read as meaning them:"
KEPT_ALL = (
    "nothing was forgotten: each remembered exchange holding that value is about something the "
    "user's message does not name or asks to keep, so each was kept"
)
KEPT_NOTE = "\n\n(Still in memory, since your message was not read as meaning them:"
KEPT_NOTES = {
    "fr": "\n\n(Toujours en mémoire, car votre message n'a pas été lu comme les visant :",
    "de": "\n\n(Noch gespeichert, weil Ihre Nachricht nicht als auf sie bezogen gelesen wurde:",
    "es": "\n\n(Todavía en memoria, porque tu mensaje no se leyó como referido a ellos:",
    "ro": "\n\n(Încă în memorie, pentru că mesajul tău nu a fost citit ca referindu-se la ele:",
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


def row_names(text: str) -> set[str]:
    """The words of a stored exchange a forget part or keep clause can name it by."""
    return row_words(text) | _kinds(_PREFIX.sub("\n", text))


def _named(rows: list[MemoryRecord], words: set[str], deleted: Iterable[MemoryRecord]) -> bool:
    """Whether a word of ``words`` names a fact of ``rows`` or ``deleted``."""
    return any(names(words, row_words(record.text)) for record in (*rows, *deleted))


def _last_groups(request: str) -> set[str]:
    """The last group of each whole value of ``request``, as ``4242`` of ``0721 555 4242``."""
    return {_GROUP.findall(form.lower())[-1] for form in whole_values(request).values()}


def _lists(
    text: str, listed: set[str], values: set[str], *, kind: frozenset[str], every: bool = False
) -> bool:
    """Whether a forget part naming ``listed``, or only the whole ``values``, names the row; with
    ``every``, a row of a kind of the table holding one as the last group of a longer value too."""
    request = text.split(_REPLY, 1)[0]
    ends = every and bool(kinds(row_names(text))) and not values.isdisjoint(_last_groups(request))
    held = ends or not values.isdisjoint(whole_values(request))
    return names(listed, row_names(text), kind=kind) or held


def _keep_read(
    rows: list[MemoryRecord], kind: frozenset[str], words: set[str], read: frozenset[str]
) -> bool:
    """Whether each of ``words``, a keep clause's, names a row of ``rows`` or is one of ``read``,
    the words naming another stored row, so a keep clause read in part lists no row."""
    return bool(words) and all(
        word in read or any(names({word}, row_names(row.text), kind=kind) for row in rows)
        for word in words
    )


def _all_else(query: str, keep: set[str]) -> bool:
    """Whether ``query`` asks for every row its keep clause does not name: the part asking to
    forget is a forget verb then a word for all, and the keep clause is one opening word then only
    words of ``keep``, for the or my, or for and."""
    match parts(query):
        case ([verb, every], [_, *named]):
            plain = FORGET.fullmatch(verb) is not None and every in EVERY
            return plain and (keep | WHOSE | AND).issuperset(named)
        case _:
            return False


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
    return not _REST.isdisjoint(parts(query)[1]) or not kept.isdisjoint(row_names(text))


def _limited(words: list[str], named: set[str]) -> bool:
    """Whether a word of ``words`` before their first value is one of ``named`` or a kind word,
    as ``card`` of ``every card 4242``, so the word for all before it asks only for those rows."""
    at = next((at for at, word in enumerate(words) if any(map(str.isdigit, word))), len(words))
    between = {name for word in words[:at] for name in (word, code_stem(word) or word)}
    return not between.isdisjoint(named) or bool(kinds(between))


def quantifies(query: str, rows: Iterable[str] | None = None) -> bool:
    """Whether a word for all in ``query`` asks for every row: within two words of a value, and,
    given ``rows``, with no word between it and a value after it that ``_limited`` reads."""
    split = clauses(query)
    function = {word for language in readings(query) for word in FUNCTION.get(language, ())}
    named = None if rows is None else {word for text in rows for word in row_words(text)} - function
    for index, clause in enumerate(split):
        if any(KEEP.fullmatch(token) for token in clause):
            continue
        for at, token in enumerate(clause):
            if token not in EVERY or (at + 1 < len(clause) and clause[at + 1] in TOPIC):
                continue
            after = clause[at + 1 : at + 3]
            limited = named is not None and _limited(after, named)
            beside = [*clause[max(0, at - 2) : at], *([] if limited else after)]
            if len(clause) == 1 and index:
                beside = split[index - 1][-1:]
            if any(char.isdigit() for char in "".join(beside)):
                return True
    return False


def _other_kinds(query: str, keep: set[str], language: str) -> bool:
    """Whether ``query`` asks for every row but the kinds it keeps: ``quantifies``, each word
    ``keep`` of its keep clauses a kind word, none a word for all, and no code word outside them."""
    forget, kept = parts(query)
    named = all(kinds({word}) for word in keep - FUNCTION.get(language, frozenset()))
    plain = EVERY.isdisjoint(kept) and not any(map(code_word, forget))
    return quantifies(query) and named and plain


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
    read: frozenset[str] = frozenset(),
) -> list[MemoryRecord]:
    """The ``records`` to keep, each a reading of ``query`` in one of its ``readings`` keeps.
    ``read`` are the words of its keep clauses naming a stored row outside ``records``."""
    rows, deleted = list(records), list(deleted)
    if not query.strip():
        return []
    kept = set[str]()
    for language in readings(query):
        beside = _beside_keep(rows, query, language, read)
        found = _unnamed(rows, text, query, deleted, session_id, language)
        kept |= {record.id for record in (found if beside is None else beside)}
    return [record for record in rows if record.id in kept]


def _beside_keep(
    rows: list[MemoryRecord], query: str, language: str, read: frozenset[str]
) -> list[MemoryRecord] | None:
    """The ``rows`` to keep beside a keep clause of ``query``: each it names or neither ``_lists``
    nor ``_all_else`` lists, so a misread keeps the row; ``None`` when it has no keep clause."""
    _, keep, listed, _ = _split(query, language)
    if listed is None:
        return None
    words, kind = keep - FUNCTION.get(language, frozenset()), read_kinds(query)
    told = not listed and _keep_read(rows, kind, words, read)
    values = set(whole_values(" ".join(parts(query)[0]))) if told else set[str]()
    every, rest = _other_kinds(query, keep, language), told and _all_else(query, words)
    return [
        record
        for record in rows
        if not (rest or _lists(record.text, listed, values, kind=kind, every=every))
        or names(keep, row_names(record.text))
    ]


def _unnamed(
    rows: list[MemoryRecord],
    text: str,
    query: str,
    deleted: list[MemoryRecord],
    session_id: str | None,
    language: str,
) -> list[MemoryRecord]:
    """The ``rows`` to keep with no keep clause: each whose request holds a value of ``text`` and
    no word of ``query``, unless it asks for every row, or names nothing and is the row
    ``just_said`` reads beside ``deleted``."""
    words, _, _, compound = _split(query, language)
    asked, values = _keys(query), _keys(text) - _keys(query) or _keys(text)
    named = compound or _named(rows, words, deleted)
    texts = [record.text for record in (*rows, *deleted)]
    every = values <= asked and (not named or quantifies(query, texts))
    said = None if named else just_said(rows, session_id, deleted)
    return [
        record
        for record in rows
        if not every
        and record.id != said
        and not values.isdisjoint(_keys(record.text.split(_REPLY, 1)[0]))
        and not names(words, row_words(record.text), kind=read_kinds(query))
    ]
