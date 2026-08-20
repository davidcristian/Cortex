"""Opt-in recall reranking policies over the ``RecallPolicy`` seam (ADR-0008).

Split from ``rerank.py`` (the port and the default ``RawRecallPolicy``) at the 300-line cap. These
three policies are opt-in, selected at the composition root by ``CORTEX_MEMORY_RECALL``; each keeps
the ``MemoryStore.search`` contract untouched and reranks above it, so both store adapters stay pure
translators. ``RerankingRecallPolicy`` blends similarity with an exponential recency decay and drops
near-duplicates; ``MmrRecallPolicy`` selects for maximal marginal relevance (diversity beyond that
near-duplicate cutoff); ``RecencyMmrRecallPolicy`` composes the two, running MMR selection over the
recency-blended relevance. The shared ``recency_blend``/``redundancy``/``greedy_mmr`` helpers live
in ``rerank_math.py`` and keep each policy to its own axis; the model-based judge is a fourth
policy, in ``rerank_judge.py`` because it holds ports rather than only maths.

Each ``select`` returns a ``Ranking`` carrying the key it ordered by and the basis naming that key
(ADR-0038). Order and membership are unchanged by that widening.
"""

from collections.abc import Sequence
from datetime import datetime

from cortex_core.memory import ScoredMemory
from cortex_core.ranking import RankBasis, RankedMemory, Ranking
from cortex_core.rerank_math import cosine, greedy_mmr, recency_blend, redundancy


class RerankingRecallPolicy:
    """Blend similarity with recency over a wider pool, drop near-duplicates, truncate to ``k``.

    ``candidate_k`` over-fetches ``k * pool_factor`` candidates. ``select`` scores each hit by its
    ``recency_blend``, sorts by that blend (stable, so equal-blend ties keep the store's
    similarity order), greedily drops a hit whose embedding cosine to an already-kept hit is
    ``>= dedup_threshold`` (identical text roundtrips to cosine 1.0, so exact duplicates and their
    paraphrases fall out), and returns the top ``k``. Each emitted ``ScoredMemory.score`` stays the
    raw cosine: order and membership reflect relevance, the score keeps the store's meaning.
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

    async def select(
        self,
        hits: Sequence[ScoredMemory],
        *,
        query: str,
        now: datetime,
        k: int,
        session_id: str | None = None,
    ) -> Ranking:
        """Rerank by the similarity+recency blend, drop near-duplicates, keep the top ``k``."""
        del query, session_id  # a geometric policy reads neither the question nor where it is
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
    """Select for maximal marginal relevance: trade query-relevance against diversity, greedily.

    Threshold dedup (``RerankingRecallPolicy``) only removes *near*-identical hits; a pool of
    distinct-but-redundant memories (several phrasings of one fact, each below the dedup cosine)
    still crowds out the rest, so the turn sees one region of the query's neighborhood ``k`` times.
    MMR instead penalizes *every* candidate by its ``redundancy`` to what is kept, so the returned
    ``k`` spread across the neighborhood (ADR-0008 rerank addendum, diversity past threshold dedup).

    ``candidate_k`` over-fetches ``k * pool_factor``. ``select`` builds the result greedily via
    ``greedy_mmr``, each step maximizing ``relevance_weight * similarity - (1 - relevance_weight) *
    redundancy`` where ``similarity`` is the hit's raw cosine (the store's score).
    ``relevance_weight`` is the MMR ``lambda``: ``1.0`` is pure relevance (top-``k`` by score,
    degenerating to ``RawRecallPolicy`` order), ``0.0`` pure diversity after the first pick. Each
    emitted ``ScoredMemory.score`` stays the raw cosine. Recency is out of scope: it is
    ``RerankingRecallPolicy``'s axis, a distinct policy.
    """

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
    ) -> Ranking:
        """Greedily keep the ``k`` hits of highest marginal relevance (relevance less penalty)."""
        # MMR weighs relevance against diversity: not the question, not the age, not the caller.
        del query, now, session_id
        return Ranking(hits=greedy_mmr(hits, k, self._marginal_relevance), basis=RankBasis.SPREAD)

    def _marginal_relevance(self, hit: ScoredMemory, kept: Sequence[ScoredMemory]) -> float:
        """The MMR objective: query-relevance discounted by redundancy against what is kept."""
        penalty = (1.0 - self._relevance_weight) * redundancy(hit, kept)
        return self._relevance_weight * hit.score - penalty


class RecencyMmrRecallPolicy:
    """MMR selection run over the reranker's recency-blended relevance instead of the raw cosine.

    ``MmrRecallPolicy`` diversifies on raw query-similarity and ``RerankingRecallPolicy`` weights
    recency; a memory that is fresh, on-topic, *and* non-redundant wants both axes at once. This
    policy composes them: the MMR greedy selection (penalize each candidate by its redundancy to
    what is kept) run with the ``recency_blend`` similarity-and-recency combination as the
    relevance term, so the returned ``k`` are recent, relevant, *and* spread across the query's
    neighborhood (ADR-0008 recency-and-diversity addendum).

    ``candidate_k`` over-fetches ``k * pool_factor``. ``select`` builds the result greedily via
    ``greedy_mmr``, each step maximizing ``relevance_weight * blend - (1 - relevance_weight) *
    redundancy`` where ``blend`` is the hit's ``recency_blend`` relevance. ``relevance_weight`` is
    the MMR ``lambda`` (relevance vs diversity); ``recency_weight`` is the blend's recency share.
    Each emitted ``ScoredMemory.score`` stays the raw cosine, as the other reranking policies.
    """

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
    ) -> Ranking:
        """Greedily keep the ``k`` of highest recency-blended marginal relevance."""
        del query, session_id  # a geometric policy reads neither the question nor where it is
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
