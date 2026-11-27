"""Read a forget of everything, the rows its words name and the words after it no reader reads."""

from collections.abc import Awaitable, Callable, Sequence

from cortex_core import forget_forms as forms
from cortex_core.forget_clauses import EVERY, FORGET, NOT, WHOSE, clauses, kept_again
from cortex_core.forget_inside import content, request
from cortex_core.forget_kinds import names
from cortex_core.forget_unnamed import TOPIC
from cortex_core.memory import MemoryRecord
from cortex_core.memory_values import code_word

Finding = Callable[[str], Awaitable[Sequence[MemoryRecord]]]
_PLACE = forms.words(forms.PLACE)


def everything(query: str) -> tuple[int, int] | None:
    """The clause of ``query`` and the place in it of the first word for all after a forget verb,
    with no negation before it, no value after it in the clause and no topic word next, unless
    that word ends the clause."""
    for index, clause in enumerate(clauses(query)):
        verb = next((at for at, token in enumerate(clause) if FORGET.fullmatch(token)), None)
        for at, token in enumerate(clause):
            rest = clause[at + 1 :]
            plain = verb is not None and verb < at and NOT.isdisjoint(clause[:at])
            valued = any(char.isdigit() for char in "".join(rest))
            topic = len(rest) > 1 and not TOPIC.isdisjoint(rest[:1])
            if plain and token in EVERY and not valued and not topic:
                return index, at
    return None


async def store_named(
    query: str, find: Finding, seen: Sequence[MemoryRecord]
) -> tuple[dict[str, set[str]], frozenset[str]]:
    """The ids of the rows, of ``seen`` or found, each word of ``query`` names, and the words that
    name one, with each code word of ``query``."""
    rows: dict[str, set[str]] = {}
    for word in sorted(content(query)):
        found = await find(word)
        rows[word] = {row.id for row in (*seen, *found) if names({word}, request(row))}
    codes = {word for clause in clauses(query) for word in clause if code_word(word)}
    return rows, frozenset({word for word, ids in rows.items() if ids} | codes)


def unread_after_every(
    query: str, place: tuple[int, int], named: frozenset[str]
) -> tuple[str, set[str]]:
    """The word for all at ``place``, where ``everything`` reads ``query``, and the words of
    ``named`` after it under a role no reader reads."""
    split, (index, at) = clauses(query), place
    every = split[index][at]
    # Words opening as a limit does, as in "all my card numbers", are left to the limit readers.
    if not (WHOSE | _PLACE | named).isdisjoint(split[index][at + 1 : at + 2]):
        split[index] = split[index][: at + 1]
    return every, kept_again(", ".join(" ".join(clause) for clause in split), every, named)
