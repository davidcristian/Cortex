"""Opt-in recall reranking policies behind the ``RecallPolicy`` port."""

from collections.abc import Sequence
from datetime import datetime

from cortex_core.memory import ScoredMemory
from cortex_core.ranking import RankBasis, RankedMemory, Ranking
from cortex_core.rerank_math import cosine, greedy_mmr, recency_blend, redundancy


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

    async def select(
        self,
        hits: Sequence[ScoredMemory],
        *,
        query: str,
        now: datetime,
        k: int,
        session_id: str | None = None,
        turn_id: str | None = None,
    ) -> Ranking:
        """Rerank by the similarity+recency blend, drop near-duplicates, keep the top ``k``."""
        del query, session_id, turn_id
        ranked = sorted(hits, key=lambda hit: self._relevance(hit, now), reverse=True)
        kept: list[ScoredMemory] = []
        for hit in ranked:
            if not any(self._is_duplicate(hit, other) for other in kept):
                kept.append(hit)
        return Ranking(
            hits=tuple(RankedMemory(hit=hit, key=self._relevance(hit, now)) for hit in kept[:k]),
            basis=RankBasis.EMBER,
        )

    def _relevance(self, hit: ScoredMemory, now: datetime) -> float:
        """The blended rank key: similarity discounted toward its recency."""
        return recency_blend(
            hit,
            now,
            half_life_seconds=self._half_life_seconds,
            recency_weight=self._recency_weight,
        )

    def _is_duplicate(self, hit: ScoredMemory, other: ScoredMemory) -> bool:
        """True when two hits' embeddings are within the dedup cosine threshold."""
        return cosine(hit.record.embedding, other.record.embedding) >= self._dedup_threshold


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

    async def select(
        self,
        hits: Sequence[ScoredMemory],
        *,
        query: str,
        now: datetime,
        k: int,
        session_id: str | None = None,
        turn_id: str | None = None,
    ) -> Ranking:
        """Greedily keep the ``k`` hits of highest marginal relevance (relevance less penalty)."""
        del query, now, session_id, turn_id
        return Ranking(hits=greedy_mmr(hits, k, self._marginal_relevance), basis=RankBasis.SPREAD)

    def _marginal_relevance(self, hit: ScoredMemory, kept: Sequence[ScoredMemory]) -> float:
        """The MMR objective: query-relevance discounted by redundancy against what is kept."""
        penalty = (1.0 - self._relevance_weight) * redundancy(hit, kept)
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

    async def select(
        self,
        hits: Sequence[ScoredMemory],
        *,
        query: str,
        now: datetime,
        k: int,
        session_id: str | None = None,
        turn_id: str | None = None,
    ) -> Ranking:
        """Greedily keep the ``k`` of highest recency-blended marginal relevance."""
        del query, session_id, turn_id
        return Ranking(
            hits=greedy_mmr(hits, k, lambda hit, kept: self._marginal_relevance(hit, kept, now)),
            basis=RankBasis.SWEEP,
        )

    def _marginal_relevance(
        self, hit: ScoredMemory, kept: Sequence[ScoredMemory], now: datetime
    ) -> float:
        """The MMR objective with the similarity-and-recency blend as the relevance term."""
        relevance = recency_blend(
            hit,
            now,
            half_life_seconds=self._half_life_seconds,
            recency_weight=self._recency_weight,
        )
        penalty = (1.0 - self._relevance_weight) * redundancy(hit, kept)
        return self._relevance_weight * relevance - penalty
