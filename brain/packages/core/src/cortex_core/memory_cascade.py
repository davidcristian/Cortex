"""Deleting a session: forget the memories that chat wrote, and its private scope."""

from cortex_core.memory import GLOBAL_SCOPE
from cortex_core.ports import MemoryStore
from cortex_core.scope import MemoryScope


class SessionMemoryCascade:
    """Forgets every memory one session wrote, and its own scope when the scope keeps it apart."""

    def __init__(self, store: MemoryStore, scope: MemoryScope) -> None:
        self._store = store
        self._scope = scope

    async def delete_session_memories(self, session_id: str) -> int:
        """Forget what the session wrote and its private scope; return how many were removed."""
        removed = await self._store.delete_written_by(session_id)
        scope = self._scope.write_scope(session_id)
        if scope == GLOBAL_SCOPE or scope != session_id:
            return removed
        return removed + await self._store.delete_scope(scope)
