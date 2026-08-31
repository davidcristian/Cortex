"""Session-delete memory cascade: forget a deleted chat's private memories (ADR-0021 delete).

A deliberately separate component from the turn-facing ``MemoryRecaller``. A turn reaches memory
only through the recaller, whose surface is record/recall and nothing else, so no tool call
(tainted or not) can ask for "forget everything"
(``test_the_recaller_exposes_no_forget_verb_so_no_turn_can_delete_memory``). The forget verb
(``MemoryStore.delete_scope``) is for out-of-band trusted callers only, and this is the one that
cascades a session delete. It composes the same ``MemoryStore`` + ``MemoryScope`` the recaller
uses, but is wired into the ``DeleteSession`` management RPC path, never into the engine's
capabilities, keeping the destructive verb off every turn.
"""

from cortex_core.memory import GLOBAL_SCOPE
from cortex_core.ports import MemoryStore
from cortex_core.scope import MemoryScope


class SessionMemoryCascade:
    """Scope-aware forget of one session's derived memories, for the session-delete path.

    The only link from a session to its memories is the namespace the configured ``MemoryScope``
    records under, so the cascade targets exactly ``write_scope(session_id)`` and runs only
    when that namespace is the session's own private space (session scoping, where the scope equals
    the ``session_id``): then those memories belong to this chat and nothing else. Under the shared
    ``GlobalMemoryScope`` the memories are the cross-conversation space every chat contributes to,
    so nothing session-private cascades and the store is left untouched.
    """

    def __init__(self, store: MemoryStore, scope: MemoryScope) -> None:
        self._store = store
        self._scope = scope

    async def delete_session_memories(self, session_id: str) -> int:
        """Forget the session's private memories; return how many were removed (0 if none).

        The ``GLOBAL_SCOPE`` guard is checked first and independently of the session-scoping one,
        so ``GLOBAL_SCOPE`` can never be handed to ``delete_scope`` (which would erase every
        conversation's memory) even for a session whose id happens to equal ``GLOBAL_SCOPE`` under
        a session policy. A policy that writes to some other shared namespace, neither the
        session's own scope nor global, is likewise never swept, since the cascade runs only when
        the write scope is the session id. Returns 0 whenever the cascade does not run.
        """
        scope = self._scope.write_scope(session_id)
        if scope == GLOBAL_SCOPE or scope != session_id:
            return 0
        return await self._store.delete_scope(scope)
