"""Read whether a forget message's words name a stored row, by a shared word or a kind word."""

from collections.abc import Iterable

from cortex_core.forget_clauses import NOT, clauses

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


def read_kinds(query: str) -> bool:
    """Whether a kind word of ``query`` may list a row: it holds no negation and no word for minus,
    either of which can make the kind word name a row to keep, as in ``N'oublie pas ma carte``."""
    return all(NOT.isdisjoint(clause) and MINUS.isdisjoint(clause) for clause in clauses(query))


def names(words: set[str], row: set[str], *, kind: bool = True) -> bool:
    """Whether the message's ``words`` name a row of words ``row``: a word both hold, or a kind
    both name when ``kind``."""
    return not words.isdisjoint(row) or (kind and not kinds(words).isdisjoint(kinds(row)))
