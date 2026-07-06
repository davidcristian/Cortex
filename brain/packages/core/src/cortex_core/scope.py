"""Memory scoping policy: which namespace a turn writes to, and reads from (ADR-0008 addendum)."""

from collections.abc import Sequence
from typing import Protocol

from cortex_core.memory import GLOBAL_SCOPE


class MemoryScope(Protocol):
    """Maps a turn's ``session_id`` to its memory write-scope and read-scopes."""

    def write_scope(self, session_id: str) -> str: ...

    def read_scopes(self, session_id: str) -> Sequence[str] | None: ...


class GlobalMemoryScope:
    """One shared space: write to ``GLOBAL_SCOPE``, recall across every memory (the v1 default).

    ``read_scopes`` returns ``None`` (no filter) so recall stays cross-session. This is the founding
    memory feature (ADR-0008 decision 3). The ``session_id`` is irrelevant to a global policy.
    """

    def write_scope(self, session_id: str) -> str:
        """Every memory lands in the one global namespace."""
        del session_id  # a global space ignores which conversation wrote the memory
        return GLOBAL_SCOPE

    def read_scopes(self, session_id: str) -> Sequence[str] | None:
        """No filter. Rank over all memories, whatever conversation they came from."""
        del session_id
        return None


class SessionMemoryScope:
    """Per-conversation isolation: a session writes to and recalls from only its own scope."""

    def write_scope(self, session_id: str) -> str:
        """Record into the conversation's own namespace."""
        return session_id

    def read_scopes(self, session_id: str) -> Sequence[str] | None:
        """Recall only the conversation's own memories."""
        return (session_id,)


# The default policy instance is stateless and immutable, so one shared singleton is safe and
# lets ``MemoryRecaller``'s default argument be a plain value (no per-call construction).
GLOBAL_MEMORY_SCOPE = GlobalMemoryScope()
