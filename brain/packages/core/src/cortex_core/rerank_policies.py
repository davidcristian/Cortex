"""Opt-in recall reranking policies over the ``RecallPolicy`` seam (ADR-0008)."""

from collections.abc import Callable, Sequence
from datetime import datetime
from math import sqrt

from cortex_core.memory import ScoredMemory


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity of two equal-length vectors; 0.0 if either has no magnitude."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    magnitude = sqrt(sum(x * x for x in a)) * sqrt(sum(x * x for x in b))
    if magnitude == 0:
        return 0.0
    return dot / magnitude


def _recency_blend(
    hit: ScoredMemory, now: datetime, *, half_life_seconds: float, recency_weight: float
) -> float:
    """The similarity-and-recency convex blend shared by the recency-aware policies."""
    age_seconds = max(0.0, (now - hit.record.at).total_seconds())
    recency = 0.5 ** (age_seconds / half_life_seconds)
    return (1.0 - recency_weight) * hit.score + recency_weight * recency


def _redundancy(hit: ScoredMemory, kept: Sequence[ScoredMemory]) -> float:
    """A hit's greatest embedding cosine to an already-kept hit; 0.0 for an empty kept set.

    A zero-magnitude embedding is cosine 0.0 to everything (``_cosine``), so it is never redundant.
    """
    return max(
        (_cosine(hit.record.embedding, other.record.embedding) for other in kept),
        default=0.0,
    )


def _greedy_mmr(
    hits: Sequence[ScoredMemory],
    k: int,
    marginal: Callable[[ScoredMemory, Sequence[ScoredMemory]], float],
) -> tuple[ScoredMemory, ...]:
    """Greedily keep the ``k`` hits of highest marginal score, recomputed against what is kept."""
    remaining = list(hits)
    kept: list[ScoredMemory] = []
    while remaining and len(kept) < k:
        best = max(remaining, key=lambda hit: marginal(hit, kept))
        kept.append(best)
        remaining.remove(best)
    return tuple(kept)


class RerankingRecallPolicy:
    """Blend similarity with recency over a wider pool, drop near-duplicates, truncate to ``k``."""

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
        return _recency_blend(
            hit,
            now,
            half_life_seconds=self._half_life_seconds,
            recency_weight=self._recency_weight,
        )

    def _is_duplicate(self, hit: ScoredMemory, other: ScoredMemory) -> bool:
        """True when two hits' embeddings are within the dedup cosine threshold."""
        return _cosine(hit.record.embedding, other.record.embedding) >= self._dedup_threshold


class MmrRecallPolicy:
    """Select for maximal marginal relevance: trade query-relevance against diversity, greedily."""

    def __init__(self, *, relevance_weight: float, pool_factor: int) -> None:
        if not 0.0 <= relevance_weight <= 1.0:
            msg = "relevance_weight must be within [0, 1]"
            raise ValueError(msg)
        if pool_factor < 1:
            msg = "pool_factor must be at least 1"
            raise ValueError(msg)
        self._relevance_weight = relevance_weight
        self._pool_factor = pool_factor

    def candidate_k(self, k: int) -> int:
        """Over-fetch a pool ``pool_factor`` times wider than the returned ``k``."""
        return k * self._pool_factor

    def select(
        self, hits: Sequence[ScoredMemory], *, now: datetime, k: int
    ) -> Sequence[ScoredMemory]:
        """Greedily keep the ``k`` hits of highest marginal relevance (relevance less penalty)."""
        del now  # MMR weighs relevance against diversity, not age
        return _greedy_mmr(hits, k, self._marginal_relevance)

    def _marginal_relevance(self, hit: ScoredMemory, kept: Sequence[ScoredMemory]) -> float:
        """The MMR objective: query-relevance discounted by redundancy against what is kept."""
        penalty = (1.0 - self._relevance_weight) * _redundancy(hit, kept)
        return self._relevance_weight * hit.score - penalty


class RecencyMmrRecallPolicy:
    """MMR selection run over the reranker's recency-blended relevance instead of the raw cosine."""

    def __init__(
        self,
        *,
        half_life_seconds: float,
        recency_weight: float,
        relevance_weight: float,
        pool_factor: int,
    ) -> None:
        if half_life_seconds <= 0:
            msg = "half_life_seconds must be positive"
            raise ValueError(msg)
        if not 0.0 <= recency_weight <= 1.0:
            msg = "recency_weight must be within [0, 1]"
            raise ValueError(msg)
        if not 0.0 <= relevance_weight <= 1.0:
            msg = "relevance_weight must be within [0, 1]"
            raise ValueError(msg)
        if pool_factor < 1:
            msg = "pool_factor must be at least 1"
            raise ValueError(msg)
        self._half_life_seconds = half_life_seconds
        self._recency_weight = recency_weight
        self._relevance_weight = relevance_weight
        self._pool_factor = pool_factor

    def candidate_k(self, k: int) -> int:
        """Over-fetch a pool ``pool_factor`` times wider than the returned ``k``."""
        return k * self._pool_factor

    def select(
        self, hits: Sequence[ScoredMemory], *, now: datetime, k: int
    ) -> Sequence[ScoredMemory]:
        """Greedily keep the ``k`` of highest recency-blended marginal relevance."""
        return _greedy_mmr(hits, k, lambda hit, kept: self._marginal_relevance(hit, kept, now))

    def _marginal_relevance(
        self, hit: ScoredMemory, kept: Sequence[ScoredMemory], now: datetime
    ) -> float:
        """The MMR objective with the similarity-and-recency blend as the relevance term."""
        relevance = _recency_blend(
            hit,
            now,
            half_life_seconds=self._half_life_seconds,
            recency_weight=self._recency_weight,
        )
        penalty = (1.0 - self._relevance_weight) * _redundancy(hit, kept)
        return self._relevance_weight * relevance - penalty
