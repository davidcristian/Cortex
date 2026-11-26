"""Read whether a forget message's words name a stored row, by a shared word or a kind word."""

from collections.abc import Iterable

from cortex_core.forget_clauses import AND, FORGET, NOT, clauses
from cortex_core.memory_values import code_stem

# A closed table: each line is one kind of fact in the note languages, English, French, German,
# Spanish and Romanian, so a message in one of them names a row stored in another.
_KINDS = (
    "card cards carte cartes karte karten kreditkarte bankkarte tarjeta tarjetas cardul cardului",
    "phone phones telephone téléphone telefon telefons telefonul teléfono telefono",
)
_KIND = {word: kind for kind, words in enumerate(_KINDS) for word in words.split()}
MINUS = frozenset({"minus", "less", "moins", "menos", "weniger", "puțin", "puţin"})
_SHORTEST = 3
_STEM = 4
_GROWN = 3


def kinds(words: Iterable[str]) -> set[int]:
    """The kinds of fact the lowercase ``words`` name by a kind word of the table."""
    return {_KIND[word] for word in words if word in _KIND}


def read_kinds(query: str) -> frozenset[str]:
    """The words of ``query`` a kind word may list a row from: each clause holding no negation and
    no word for minus, which can make it name a row to keep, as in ``N'oublie pas ma carte``."""
    return frozenset(
        word
        for clause in clauses(query)
        if NOT.isdisjoint(clause) and MINUS.isdisjoint(clause)
        for token in clause
        for word in (token, code_stem(token) or token)
    )


def names(words: set[str], row: set[str], *, kind: frozenset[str] | None = None) -> bool:
    """Whether the message's ``words`` name a row of words ``row``: a word both hold, or a kind
    both name, read only from the words of ``kind`` when given."""
    listing = words if kind is None else words & kind
    return not words.isdisjoint(row) or not kinds(listing).isdisjoint(kinds(row))


def verbed(query: str) -> set[str]:
    """The words of each clause of ``query`` holding a forget verb."""
    held = (clause for clause in clauses(query) if any(map(FORGET.fullmatch, clause)))
    return {token for clause in held for token in clause}


def shorter(word: str) -> list[str]:
    """``word`` less its last one or two letters, each of ``_SHORTEST`` letters or more."""
    return [word[:-cut] for cut in (1, 2) if len(word) - cut >= _SHORTEST]


def extends(word: str, row: set[str]) -> bool:
    """Whether ``word`` is a word of ``row`` with one or two letters added, as ``codes`` of
    ``code`` or ``Spinde`` of ``spind``, the way a word in another number is formed."""
    return not row.isdisjoint(shorter(word))


def grows(word: str, row: set[str]) -> bool:
    """Whether ``word`` is three or more letters longer than a word of ``row`` and starts with it or
    with it less its last letter, four letters at least, as ``cardurile`` of ``cardul``."""
    return any(
        len(word) - len(name) >= _GROWN and word.startswith(stem)
        for name in row
        for stem in (name, name[:-1])
        if len(stem) >= _STEM
    )


def prefixes(word: str) -> list[str]:
    """The starts of ``word`` a word ``word`` ``grows`` from starts with."""
    return [word[:end] for end in range(_STEM, len(word) - _GROWN + 1)]


def reads(words: set[str], row: set[str], stems: set[str]) -> bool:
    """Whether ``words`` name the row of words ``row``, or one ``extends`` a word of ``stems``, the
    row's words that can name it, as ``lockers`` and ``dulapul`` name the row holding ``locker``."""
    return names(words, row) or any(extends(word, stems) for word in words)


def limited(words: list[str], named: set[str]) -> bool:
    """Whether a word of ``words`` before their first value is a kind word or one a word of
    ``named`` starts, as ``card`` of ``every card 4242`` or ``lockers`` beside a row holding
    ``locker``, so the word for all before it asks only for those rows."""
    at = next((at for at, word in enumerate(words) if _valued(word)), len(words))
    between = {name for word in words[:at] for name in (word, code_stem(word) or word)}
    return bool(kinds(between)) or any(word.startswith(name) for word in between for name in named)


def _valued(word: str) -> bool:
    """Whether ``word`` holds a digit, as a value or a group of one does."""
    return any(map(str.isdigit, word))


def before_every(clause: list[str], end: int, named: set[str] | None) -> list[str]:
    """The two words of ``clause`` before ``end`` that a word for all there reads a value from:
    none, given ``named``, when the words before that value, back to a forget verb or a word for
    and, are ``limited``, as in ``the card 4242 everywhere``."""
    near = clause[max(0, end - 2) : end]
    first = next((at for at in range(max(0, end - 2), end) if _valued(clause[at])), None)
    if named is None or first is None:
        return near
    opens = (at + 1 for at in range(first) if clause[at] in AND or FORGET.fullmatch(clause[at]))
    return [] if limited(clause[max(opens, default=0) : first], named) else near
