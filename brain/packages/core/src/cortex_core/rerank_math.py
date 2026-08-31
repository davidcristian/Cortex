"""Scoring helpers shared by the heuristic recall policies (ADR-0008, ADR-0038).

Pure functions over pure data: a cosine, the similarity-and-recency blend, a hit's redundancy
against an already-kept set, and the greedy maximal-marginal-relevance walk. Each policy in
``rerank_policies.py`` is then only its own axis plus a basis.
"""

from collections.abc import Callable, Sequence
from datetime import datetime
from math import sqrt

from cortex_core.memory import ScoredMemory
from cortex_core.ranking import RankedMemory


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity of two equal-length vectors; 0.0 if either has no magnitude."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    magnitude = sqrt(sum(x * x for x in a)) * sqrt(sum(x * x for x in b))
    if magnitude == 0:
        return 0.0
    return dot / magnitude


def recency_blend(
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


def redundancy(hit: ScoredMemory, kept: Sequence[ScoredMemory]) -> float:
    """A hit's greatest embedding cosine to an already-kept hit; 0.0 for an empty kept set.

    A zero-magnitude embedding is cosine 0.0 to everything (``cosine``), so it is never redundant.
    """
    return max(
        (cosine(hit.record.embedding, other.record.embedding) for other in kept),
        default=0.0,
    )


def greedy_mmr(
    hits: Sequence[ScoredMemory],
    k: int,
    marginal: Callable[[ScoredMemory, Sequence[ScoredMemory]], float],
) -> tuple[RankedMemory, ...]:
    """Greedily keep the ``k`` hits of highest marginal score, recomputed against what is kept.

    ``marginal(hit, kept)`` scores a candidate given the current kept set. Candidates are scanned in
    the store's similarity order and only a strict improvement displaces the incumbent, so a tie
    keeps that order (e.g. the all-zero redundancy of the first pick keeps the most-similar hit).

    Each pick keeps the marginal score it was chosen on as its rank key (ADR-0038). Keys are not
    comparable between picks, which is why the ``SPREAD``/``SWEEP`` bases declare them so: a key was
    measured against whatever was already kept, so a later pick's key is on a harder scale.
    """
    remaining = list(hits)
    kept: list[ScoredMemory] = []
    ranked: list[RankedMemory] = []
    while remaining and len(kept) < k:
        best = max(remaining, key=lambda hit: marginal(hit, kept))
        ranked.append(RankedMemory(hit=best, key=marginal(best, kept)))
        kept.append(best)
        remaining.remove(best)
    return tuple(ranked)
