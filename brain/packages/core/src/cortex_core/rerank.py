"""Recall reranking seam: the ``RecallPolicy`` port and its default no-op policy (ADR-0008).

v1 recall was raw top-k cosine. A ``RecallPolicy`` is the pure seam that turns the over-fetched
candidate pool ``MemoryStore.search`` returns into the final ``k`` hits a turn sees: it may reorder
by more than similarity (recency) and drop near-duplicates before truncating to ``k``. It lives in
the ``MemoryRecaller`` use-case, not the store, because it needs the recaller's ``Clock`` and
composes recency with dedup in one pass the pgvector ``ORDER BY <=> LIMIT`` cannot express, above
the unchanged ``MemoryStore`` port (the ``MemoryScope``/``HistoryWindow`` pattern).

This module holds the port and ``RawRecallPolicy`` (the default: v1 behavior exactly, so reranking
is opt-in). The opt-in heuristic policies (recency, MMR diversity, and their recency-and-diversity
composition) live in ``rerank_policies.py``, their shared math in ``rerank_math.py``, and the
model-based judge in ``rerank_judge.py`` (all split off at the 300-line cap).

``select`` is ``async`` and returns a ``Ranking`` rather than a bare sequence (ADR-0038): the first
so a policy may call the model, the second so the key a policy ranked by travels with the hits it
kept. Both landed as one widening because three deferred consumers wanted one each.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from cortex_core.memory import ScoredMemory
from cortex_core.ranking import RankBasis, RankedMemory, Ranking


class RecallPolicy(Protocol):
    """Turns an over-fetched candidate pool into the final ``k`` hits the turn sees.

    ``candidate_k`` is how many candidates ``recall`` fetches from the store for a request of
    ``k`` (a policy that reranks wants a wider pool than it returns). ``select`` reorders and
    prunes that pool, returning a ``Ranking`` of at most ``k`` hits; ``now`` is the recall time, so
    a recency-aware policy needs no clock of its own. Both keep the store's ``search`` contract
    untouched.

    ``select`` is ``async`` so a policy may run a model pass (ADR-0038 decision 7). A policy that
    does must fully drain and close its stream before returning, because the GPU lease is a
    non-reentrant lock held for a stream's lifetime and the turn's own reply acquires it after
    selection has completed (decision 8). Every heuristic policy simply has a synchronous body.

    ``session_id`` names the recall the caller is making, and it is optional for the reason
    ``progress`` is optional on ``HistoryWindow.select`` and ``stops`` is optional on
    ``drain_text``: only a policy that reports something has any use for it, so a caller with no
    identity to give passes none and the policies that never log ignore it. ``MemoryRecaller``
    already holds one, so nothing is plumbed to reach here (ADR-0038 named-recall addendum).

    **It is an id and never content.** The pool and the ``query`` a policy is handed are
    conversation text, which no line of this repo's logs may carry, so what a policy may say about
    where it is happening is the caller's own opaque handle and nothing else. That is the whole
    reason this is a separate parameter rather than a widening of ``query``.
    """

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
    """v1 behavior: fetch exactly ``k`` and keep the store's similarity order, unchanged.

    ``candidate_k`` is ``k`` (no over-fetch) and ``select`` is ``hits[:k]``. The store already
    returns a similarity-sorted pool of length ``k``, so recall pays no extra fetch and its result
    is byte-for-byte the pre-reranking behavior. This is the default, so reranking is opt-in. Its
    rank key is the store's own cosine, which is the ``ECHO`` basis (ADR-0038).
    """

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
        # nothing to name a session on; the parameter is the port's shape, not this policy's need.
        del query, now, session_id
        return Ranking(
            hits=tuple(RankedMemory(hit=hit, key=hit.score) for hit in hits[:k]),
            basis=RankBasis.ECHO,
        )


# The default policy is stateless and immutable, so one shared singleton is safe and lets
# ``MemoryRecaller``'s default argument be a plain value (mirrors ``GLOBAL_MEMORY_SCOPE``).
RAW_RECALL_POLICY = RawRecallPolicy()
