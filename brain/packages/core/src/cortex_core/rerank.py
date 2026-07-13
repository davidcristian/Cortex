"""Recall reranking policy: reorder and prune a candidate pool into what the turn sees (ADR-0008).

v1 recall was raw top-k cosine. A ``RecallPolicy`` is the pure seam that turns an over-fetched
candidate pool into the final hits: it may reorder by more than similarity (recency), and drop
near-duplicates, before truncating to ``k``. It lives in the ``MemoryRecaller`` use-case, not the
store, because it needs the ``Clock`` the recaller owns (the store has none) and composes recency
with dedup in one pass the pgvector ``ORDER BY <=> LIMIT`` cannot express. The ``MemoryStore`` port
is unchanged: ``search`` still returns top-k by cosine, most-similar first; the policy reranks above
it, so both adapters stay pure translators (the ``MemoryScope``/``HistoryWindow`` pattern).

``RawRecallPolicy`` (the default) is v1 behavior exactly, so recall stays byte-for-byte identical
unless a deployment opts into ``RerankingRecallPolicy``, which blends similarity with an exponential
recency decay and greedily drops near-duplicate memories. Further policies (a model-based reranker,
maximal-marginal-relevance diversity) are additions here, behind the unchanged port.
"""

from collections.abc import Sequence
from datetime import datetime
from math import sqrt
from typing import Protocol

from cortex_core.memory import ScoredMemory


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity of two equal-length vectors; 0.0 if either has no magnitude."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    magnitude = sqrt(sum(x * x for x in a)) * sqrt(sum(x * x for x in b))
    if magnitude == 0:
        return 0.0
    return dot / magnitude


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


class RerankingRecallPolicy:
    """Blend similarity with recency over a wider pool, drop near-duplicates, truncate to ``k``.

    ``candidate_k`` over-fetches ``k * pool_factor`` candidates. ``select`` scores each hit by a
    convex blend ``(1 - recency_weight) * similarity + recency_weight * recency``, where
    ``recency`` is an exponential decay ``0.5 ** (age / half_life)`` over an age floored at 0, so a
    future-dated record (clock skew or a corrupt row) is treated as maximally recent, cannot
    outweigh a fresh one, and never overflows the exponent. It sorts by that blend
    (stable, so equal-blend ties keep the store's similarity order), greedily drops a hit whose
    embedding cosine to an already-kept hit is ``>= dedup_threshold`` (identical text roundtrips
    to cosine 1.0, so exact duplicates and their paraphrases fall out), and returns the top ``k``.
    Each emitted
    ``ScoredMemory.score`` stays the raw cosine similarity: order and membership reflect relevance,
    the reported score keeps the store's meaning.
    """

    def __init__(
        self,
        *,
        half_life_seconds: float,
        recency_weight: float,
        dedup_threshold: float,
        pool_factor: int,
    ) -> None:
        if half_life_seconds <= 0:
            msg = "half_life_seconds must be positive"
            raise ValueError(msg)
        if not 0.0 <= recency_weight <= 1.0:
            msg = "recency_weight must be within [0, 1]"
            raise ValueError(msg)
        if not 0.0 < dedup_threshold <= 1.0:
            msg = "dedup_threshold must be within (0, 1]"
            raise ValueError(msg)
        if pool_factor < 1:
            msg = "pool_factor must be at least 1"
            raise ValueError(msg)
        self._half_life_seconds = half_life_seconds
        self._recency_weight = recency_weight
        self._dedup_threshold = dedup_threshold
        self._pool_factor = pool_factor

    def candidate_k(self, k: int) -> int:
        """Over-fetch a pool ``pool_factor`` times wider than the returned ``k``."""
        return k * self._pool_factor

    def select(
        self, hits: Sequence[ScoredMemory], *, now: datetime, k: int
    ) -> Sequence[ScoredMemory]:
        """Rerank by the similarity+recency blend, drop near-duplicates, keep the top ``k``."""
        ranked = sorted(hits, key=lambda hit: self._relevance(hit, now), reverse=True)
        kept: list[ScoredMemory] = []
        for hit in ranked:
            if not any(self._is_duplicate(hit, other) for other in kept):
                kept.append(hit)
        return tuple(kept[:k])

    def _relevance(self, hit: ScoredMemory, now: datetime) -> float:
        """The blended rank key: similarity discounted toward its recency."""
        # Floor the age at 0 so a future-dated record (clock skew or a corrupt/hand-inserted row)
        # is treated as maximally recent. This both realizes the clamp (recency stays in (0, 1])
        # and keeps the exponent non-positive, so ``0.5 ** x`` can never overflow to OverflowError.
        age_seconds = max(0.0, (now - hit.record.at).total_seconds())
        recency = 0.5 ** (age_seconds / self._half_life_seconds)
        return (1.0 - self._recency_weight) * hit.score + self._recency_weight * recency

    def _is_duplicate(self, hit: ScoredMemory, other: ScoredMemory) -> bool:
        """True when two hits' embeddings are within the dedup cosine threshold."""
        return _cosine(hit.record.embedding, other.record.embedding) >= self._dedup_threshold


# The default policy is stateless and immutable, so one shared singleton is safe and lets
# ``MemoryRecaller``'s default argument be a plain value (mirrors ``GLOBAL_MEMORY_SCOPE``).
RAW_RECALL_POLICY = RawRecallPolicy()
