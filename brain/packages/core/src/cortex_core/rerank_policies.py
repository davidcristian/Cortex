"""Opt-in recall reranking policies over the ``RecallPolicy`` seam (ADR-0008).

Split from ``rerank.py`` (the port and the default ``RawRecallPolicy``) at the 300-line cap. These
three policies are opt-in, selected at the composition root by ``CORTEX_MEMORY_RECALL``; each keeps
the ``MemoryStore.search`` contract untouched and reranks above it, so both store adapters stay pure
translators. ``RerankingRecallPolicy`` blends similarity with an exponential recency decay and drops
near-duplicates; ``MmrRecallPolicy`` selects for maximal marginal relevance (diversity beyond that
near-duplicate cutoff); ``RecencyMmrRecallPolicy`` composes the two, running MMR selection over the
recency-blended relevance. The shared ``_recency_blend``/``_redundancy``/``_greedy_mmr`` helpers
keep each policy to its own axis; a further model-based reranker is one more addition here.
"""

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
    """The similarity-and-recency convex blend shared by the recency-aware policies.

    ``(1 - recency_weight) * similarity + recency_weight * recency``, where ``recency`` is the
    exponential decay ``0.5 ** (age / half_life)`` over an age floored at 0, so a future-dated
    record (clock skew or a corrupt/hand-inserted row) is treated as maximally recent, cannot
    outweigh a fresh one, and keeps the exponent non-positive so ``0.5 ** x`` never overflows.
    """
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
    """Greedily keep the ``k`` hits of highest marginal score, recomputed against what is kept.

    ``marginal(hit, kept)`` scores a candidate given the current kept set. Candidates are scanned in
    the store's similarity order and only a strict improvement displaces the incumbent, so a tie
    keeps that order (e.g. the all-zero redundancy of the first pick keeps the most-similar hit).
    """
    remaining = list(hits)
    kept: list[ScoredMemory] = []
    while remaining and len(kept) < k:
        best = max(remaining, key=lambda hit: marginal(hit, kept))
        kept.append(best)
        remaining.remove(best)
    return tuple(kept)


class RerankingRecallPolicy:
    """Blend similarity with recency over a wider pool, drop near-duplicates, truncate to ``k``.

    ``candidate_k`` over-fetches ``k * pool_factor`` candidates. ``select`` scores each hit by its
    ``_recency_blend``, sorts by that blend (stable, so equal-blend ties keep the store's
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
    """Select for maximal marginal relevance: trade query-relevance against diversity, greedily.

    Threshold dedup (``RerankingRecallPolicy``) only removes *near*-identical hits; a pool of
    distinct-but-redundant memories (several phrasings of one fact, each below the dedup cosine)
    still crowds out the rest, so the turn sees one region of the query's neighborhood ``k`` times.
    MMR instead penalizes *every* candidate by its ``_redundancy`` to what is kept, so the returned
    ``k`` spread across the neighborhood (ADR-0008 rerank addendum, diversity past threshold dedup).

    ``candidate_k`` over-fetches ``k * pool_factor``. ``select`` builds the result greedily via
    ``_greedy_mmr``, each step maximizing ``relevance_weight * similarity - (1 - relevance_weight) *
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
    """MMR selection run over the reranker's recency-blended relevance instead of the raw cosine.

    ``MmrRecallPolicy`` diversifies on raw query-similarity and ``RerankingRecallPolicy`` weights
    recency; a memory that is fresh, on-topic, *and* non-redundant wants both axes at once. This
    policy composes them: the MMR greedy selection (penalize each candidate by its redundancy to
    what is kept) run with the ``_recency_blend`` similarity-and-recency combination as the
    relevance term, so the returned ``k`` are recent, relevant, *and* spread across the query's
    neighborhood (ADR-0008 recency-and-diversity addendum).

    ``candidate_k`` over-fetches ``k * pool_factor``. ``select`` builds the result greedily via
    ``_greedy_mmr``, each step maximizing ``relevance_weight * blend - (1 - relevance_weight) *
    redundancy`` where ``blend`` is the hit's ``_recency_blend`` relevance. ``relevance_weight`` is
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
