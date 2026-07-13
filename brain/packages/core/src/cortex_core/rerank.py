"""Recall reranking seam: the ``RecallPolicy`` port and its default no-op policy (ADR-0008)."""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from cortex_core.memory import ScoredMemory


class RecallPolicy(Protocol):
    """Turns an over-fetched candidate pool into the final ``k`` hits the turn sees."""

    def candidate_k(self, k: int) -> int: ...

    def select(
        self, hits: Sequence[ScoredMemory], *, now: datetime, k: int
    ) -> Sequence[ScoredMemory]: ...


class RawRecallPolicy:
    """v1 behavior: fetch exactly ``k`` and keep the store's similarity order, unchanged."""

    def candidate_k(self, k: int) -> int:
        """No over-fetch: the pool is exactly the ``k`` the caller asked for."""
        return k

    def select(
        self, hits: Sequence[ScoredMemory], *, now: datetime, k: int
    ) -> Sequence[ScoredMemory]:
        """Keep the store's order, truncated to ``k`` (``now`` is irrelevant to raw recall)."""
        del now  # raw recall does not weight by age
        return tuple(hits[:k])


# The default policy is stateless and immutable, so one shared singleton is safe and lets
# ``MemoryRecaller``'s default argument be a plain value (mirrors ``GLOBAL_MEMORY_SCOPE``).
RAW_RECALL_POLICY = RawRecallPolicy()
