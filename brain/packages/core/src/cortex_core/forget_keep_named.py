"""Find the stored rows a forget message's keep clause names, matched by a forget call or not."""

from collections.abc import Sequence

from cortex_core.forget_clauses import AND, EVERY, clauses, parts
from cortex_core.forget_inside import content, request
from cortex_core.forget_kinds import extends, grows, names, prefixes, read_kinds, shorter, verbed
from cortex_core.forget_languages import FUNCTION
from cortex_core.forget_unnamed import asks_to_keep, keep_words, row_names
from cortex_core.memory import MemoryRecord
from cortex_core.ports import MemoryStore
from cortex_core.scope import MemoryScope
from cortex_core.tools import ToolCall

_FUNCTION = frozenset(word for words in FUNCTION.values() for word in words)


async def keep_named(
    store: MemoryStore, scope: MemoryScope, call: ToolCall, limit: int
) -> tuple[dict[str, str], frozenset[str]]:
    """The rows the keep clause of the call's message names, row id to its text on one line, and
    the words of that clause naming one."""
    query = call.stamp.query
    named: dict[str, str] = {}
    read: set[str] = set()
    for word in sorted(keep_words(query)):
        scopes = scope.read_scopes(call.stamp.session_id)
        for record in await store.find_text(word, limit=limit, scopes=scopes):
            if asks_to_keep(record.text, query):
                named[record.id] = " ".join(record.text.split())
            if names({word}, row_names(record.text), kind=read_kinds(query)):
                read.add(word)
    return named, frozenset(read)


def forget_words(query: str) -> set[str]:
    """The words of the part of ``query`` asking to forget that can name a row: none when a word
    for all ends a clause or is before a word for and, which asks for every row."""
    every = any(
        token in EVERY and clause[at + 1 : at + 2] in ([], *([word] for word in AND))
        for clause in clauses(query)
        for at, token in enumerate(clause)
    )
    return set[str]() if every else content(query, " ".join(parts(query)[0]))


async def forget_named(
    store: MemoryStore, scope: MemoryScope, call: ToolCall, limit: int, gone: Sequence[MemoryRecord]
) -> list[MemoryRecord]:
    """The stored rows the chat can read, and those of ``gone``, the rows the turn deleted, whose
    request a word of ``forget_words`` names or, in a forget verb's clause, ``extends``, else each
    such a word ``grows`` from, of the words ``_apart`` leaves."""
    query = call.stamp.query
    words = forget_words(query)
    scopes = scope.read_scopes(call.stamp.session_id)
    rows = list(gone)
    for word in sorted(words):
        rows += await store.find_text(word, limit=limit, scopes=scopes)
    told = words & verbed(query)
    unread = {word for word in told if not any(names({word}, request(row)) for row in rows)}
    for stem in sorted({stem for word in unread for stem in (*shorter(word), *prefixes(word))}):
        rows += await store.find_text(stem, limit=limit, scopes=scopes)
    asked = _apart({row.id: request(row) - _FUNCTION for row in rows})
    named = [
        row
        for row in rows
        if names(words, request(row)) or any(extends(word, asked[row.id]) for word in unread)
    ]
    grown = [row for row in rows if any(grows(word, asked[row.id]) for word in unread)]
    return named or grown


def _apart(asked: dict[str, set[str]]) -> dict[str, set[str]]:
    """Each row's words of ``asked`` less those every request of two or more holds, as
    ``remember``, which tell no row apart."""
    shared = set[str].intersection(*asked.values()) if len(asked) > 1 else set[str]()
    return {row: words - shared for row, words in asked.items()}
