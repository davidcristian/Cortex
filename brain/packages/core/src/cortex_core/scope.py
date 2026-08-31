"""Memory scoping policy: which namespace a turn writes to, and reads from (ADR-0008 addendum).

A memory lives in a ``scope`` (an opaque namespace string on ``MemoryRecord``). A
``MemoryScope`` is the pure policy that maps a turn's ``session_id`` to the scope it records
under and the scopes it recalls from, forming the seam between "this turn" and the ``MemoryStore``.
It is applied only in the ``MemoryRecaller`` use-case: the store filters by whatever scopes it
is handed, the policy selects them, so scoping is a policy swap, never a port change.

Two reference policies ship. ``GlobalMemoryScope`` keeps the v1 one-global-space behavior, recall
across every conversation, and is the default; ``SessionMemoryScope`` isolates each conversation's
memory to itself. Further policies (a session+global union, namespaced buckets) are additions
here, behind the unchanged port.
"""

from collections.abc import Sequence
from typing import Protocol

from cortex_core.memory import GLOBAL_SCOPE


class MemoryScope(Protocol):
    """Maps a turn's ``session_id`` to its memory write-scope and read-scopes.

    ``write_scope`` is the single namespace a turn records into. ``read_scopes`` is the set of
    namespaces recall ranks over. ``None`` means "all scopes" (an unfiltered, global search),
    a sequence restricts to exactly those. The two need not agree: a policy may write narrowly
    yet read widely (or the reverse).
    """

    def write_scope(self, session_id: str) -> str: ...

    def read_scopes(self, session_id: str) -> Sequence[str] | None: ...


class GlobalMemoryScope:
    """One shared space: write to ``GLOBAL_SCOPE``, recall across every memory (the v1 default).

    ``read_scopes`` returns ``None`` (no filter) so recall stays cross-session (ADR-0008
    decision 3). The ``session_id`` is unused by a global policy.
    """

    def write_scope(self, session_id: str) -> str:
        """Every memory lands in the one global namespace."""
        del session_id  # the global namespace does not depend on which conversation wrote it
        return GLOBAL_SCOPE

    def read_scopes(self, session_id: str) -> Sequence[str] | None:
        """No filter. Rank over all memories, whatever conversation they came from."""
        del session_id
        return None


class SessionMemoryScope:
    """Per-conversation isolation: a session writes to and recalls from only its own scope.

    ``write_scope`` and ``read_scopes`` are both keyed on the ``session_id``, so a memory recorded
    in one conversation never surfaces in another. Adopted via ``CORTEX_MEMORY_SCOPE=session``.
    """

    def write_scope(self, session_id: str) -> str:
        """Record into the conversation's own namespace."""
        return session_id

    def read_scopes(self, session_id: str) -> Sequence[str] | None:
        """Recall only the conversation's own memories."""
        return (session_id,)


# The default policy instance is stateless and immutable, so one shared singleton is safe and
# lets ``MemoryRecaller``'s default argument be a plain value (no per-call construction).
GLOBAL_MEMORY_SCOPE = GlobalMemoryScope()
