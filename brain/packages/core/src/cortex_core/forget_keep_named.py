"""Find the stored rows a forget message's keep clause names, matched by a forget call or not."""

from cortex_core.forget_unnamed import asks_to_keep, keep_words
from cortex_core.ports import MemoryStore
from cortex_core.scope import MemoryScope
from cortex_core.tools import ToolCall


async def keep_named(
    store: MemoryStore, scope: MemoryScope, call: ToolCall, limit: int
) -> dict[str, str]:
    """The rows the keep clause of the call's message names, row id to its text on one line."""
    query = call.stamp.query
    named: dict[str, str] = {}
    for word in sorted(keep_words(query)):
        scopes = scope.read_scopes(call.stamp.session_id)
        for record in await store.find_text(word, limit=limit, scopes=scopes):
            if asks_to_keep(record.text, query):
                named[record.id] = " ".join(record.text.split())
    return named
