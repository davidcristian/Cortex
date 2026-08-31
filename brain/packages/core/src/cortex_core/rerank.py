"""Recall reranking seam: the ``RecallPolicy`` port and its default no-op policy (ADR-0008)."""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from cortex_core.memory import ScoredMemory
from cortex_core.ranking import RankBasis, RankedMemory, Ranking


class RecallPolicy(Protocol):
    """Turns an over-fetched candidate pool into the final ``k`` hits the turn sees."""

    def candidate_k(self, k: int) -> int: ...

    async def select(
        self,
        hits: Sequence[ScoredMemory],
        *,
        query: str,
        now: datetime,
        k: int,
        session_id: str | None = None,
    ) -> Ranking: ...


class RawRecallPolicy:
    """v1 behavior: fetch exactly ``k`` and keep the store's similarity order, unchanged."""

    def candidate_k(self, k: int) -> int:
        """No over-fetch: the pool is exactly the ``k`` the caller asked for."""
        return k

    async def select(
        self,
        hits: Sequence[ScoredMemory],
        *,
        query: str,
        now: datetime,
        k: int,
        session_id: str | None = None,
    ) -> Ranking:
        """Keep the store's order, truncated to ``k`` (only ``k`` matters to raw recall)."""
        # Raw recall reads neither the question nor the age, and reports nothing, so it has
        # nothing to name a session on; the parameter is the port's shape rather than this
        # policy's need.
        del query, now, session_id
        return Ranking(
            hits=tuple(RankedMemory(hit=hit, key=hit.score) for hit in hits[:k]),
            basis=RankBasis.ECHO,
        )


# The default policy is stateless and immutable, so one shared singleton is safe and lets
# ``MemoryRecaller``'s default argument be a plain value (mirrors ``GLOBAL_MEMORY_SCOPE``).
RAW_RECALL_POLICY = RawRecallPolicy()
