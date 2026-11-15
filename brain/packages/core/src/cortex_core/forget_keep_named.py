"""Find the stored rows a forget message's keep clause names, matched by a forget call or not."""

from collections.abc import Sequence

from cortex_core.forget_clauses import AND, EVERY, clauses, parts
from cortex_core.forget_inside import content, request
from cortex_core.forget_kinds import names, read_kinds
from cortex_core.forget_unnamed import asks_to_keep, keep_words, row_names
from cortex_core.memory import MemoryRecord
from cortex_core.ports import MemoryStore
from cortex_core.scope import MemoryScope
from cortex_core.tools import ToolCall


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


async def forget_named(
    store: MemoryStore, scope: MemoryScope, call: ToolCall, limit: int, gone: Sequence[MemoryRecord]
) -> list[MemoryRecord]:
    """The stored rows the chat can read, and those of ``gone``, the rows the turn deleted, whose
    request a word of the part of the call's message asking to forget names: none when a word
    for all ends a clause or is before a word for and, which asks for every row."""
    query = call.stamp.query
    every = any(
        token in EVERY and clause[at + 1 : at + 2] in ([], *([word] for word in AND))
        for clause in clauses(query)
        for at, token in enumerate(clause)
    )
    words = set[str]() if every else content(query, " ".join(parts(query)[0]))
    scopes = scope.read_scopes(call.stamp.session_id)
    rows = list(gone)
    for word in sorted(words):
        rows += await store.find_text(word, limit=limit, scopes=scopes)
    return [row for row in rows if names(words, request(row))]
