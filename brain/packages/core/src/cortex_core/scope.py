"""Memory scoping policy: which namespace a turn writes to, and reads from."""

from collections.abc import Sequence
from typing import Protocol

from cortex_core.memory import GLOBAL_SCOPE


class MemoryScope(Protocol):
    """Maps a turn's ``session_id`` to its memory write-scope and read-scopes."""

    def write_scope(self, session_id: str) -> str: ...

    def read_scopes(self, session_id: str) -> Sequence[str] | None: ...


class GlobalMemoryScope:
    """One shared space: write to ``GLOBAL_SCOPE``, recall across every memory (the v1 default)."""

    def write_scope(self, session_id: str) -> str:
        """Every memory is written to the one global namespace."""
        del session_id
        return GLOBAL_SCOPE

    def read_scopes(self, session_id: str) -> Sequence[str] | None:
        """No filter."""
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


GLOBAL_MEMORY_SCOPE = GlobalMemoryScope()
