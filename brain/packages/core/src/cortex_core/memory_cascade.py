"""Deleting a session: forget the memories that only that chat produced."""

from cortex_core.memory import GLOBAL_SCOPE
from cortex_core.ports import MemoryStore
from cortex_core.scope import MemoryScope


class SessionMemoryCascade:
    """Forgets one session's own memories, when the scope in use keeps them apart."""

    def __init__(self, store: MemoryStore, scope: MemoryScope) -> None:
        self._store = store
        self._scope = scope

    async def delete_session_memories(self, session_id: str) -> int:
        """Forget the session's private memories; return how many were removed (0 if none)."""
        scope = self._scope.write_scope(session_id)
        if scope == GLOBAL_SCOPE or scope != session_id:
            return 0
        return await self._store.delete_scope(scope)
