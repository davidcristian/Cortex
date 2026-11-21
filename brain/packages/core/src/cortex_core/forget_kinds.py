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


def bare(word: str) -> set[str]:
    """``word`` and its form less the Romanian article ``ul``, as ``dulap`` of ``dulapul``."""
    return {word, word.removesuffix("ul")}


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
