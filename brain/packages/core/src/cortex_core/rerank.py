"""Recall reranking seam: the ``RecallPolicy`` port and its default no-op policy (ADR-0008).

v1 recall was raw top-k cosine. A ``RecallPolicy`` is the pure seam that turns the over-fetched
candidate pool ``MemoryStore.search`` returns into the final ``k`` hits a turn sees: it may reorder
by more than similarity (recency) and drop near-duplicates before truncating to ``k``. It lives in
the ``MemoryRecaller`` use-case, not the store, because it needs the recaller's ``Clock`` and
composes recency with dedup in one pass the pgvector ``ORDER BY <=> LIMIT`` cannot express, above
the unchanged ``MemoryStore`` port (the ``MemoryScope``/``HistoryWindow`` pattern).

This module holds the port and ``RawRecallPolicy`` (the default: v1 behavior exactly, so reranking
is opt-in). The opt-in reranking policies (recency, MMR diversity, and their recency-and-diversity
composition) and their shared math live in ``rerank_policies.py`` (split off at the 300-line cap).
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from cortex_core.memory import ScoredMemory


class RecallPolicy(Protocol):
    """Turns an over-fetched candidate pool into the final ``k`` hits the turn sees.

    ``candidate_k`` is how many candidates ``recall`` fetches from the store for a request of
    ``k`` (a policy that reranks wants a wider pool than it returns). ``select`` reorders and
    prunes that pool, returning at most ``k`` hits; ``now`` is the recall time, so a recency-aware
    policy needs no clock of its own. Both keep the store's ``search`` contract untouched.
    """

    def candidate_k(self, k: int) -> int: ...

    def select(
        self, hits: Sequence[ScoredMemory], *, now: datetime, k: int
    ) -> Sequence[ScoredMemory]: ...


class RawRecallPolicy:
    """v1 behavior: fetch exactly ``k`` and keep the store's similarity order, unchanged.

    ``candidate_k`` is ``k`` (no over-fetch) and ``select`` is ``hits[:k]``. The store already
    returns a similarity-sorted pool of length ``k``, so recall pays no extra fetch and its result
    is byte-for-byte the pre-reranking behavior. This is the default, so reranking is opt-in.
    """

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
