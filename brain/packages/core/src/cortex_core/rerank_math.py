"""Scoring helpers shared by the heuristic recall policies."""

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
    """The similarity-and-recency convex blend shared by the recency-aware policies."""
    age_seconds = max(0.0, (now - hit.record.at).total_seconds())
    recency = 0.5 ** (age_seconds / half_life_seconds)
    return (1.0 - recency_weight) * hit.score + recency_weight * recency


def redundancy(hit: ScoredMemory, kept: Sequence[ScoredMemory]) -> float:
    """A hit's greatest embedding cosine to an already-kept hit; 0.0 for an empty kept set."""
    return max(
        (cosine(hit.record.embedding, other.record.embedding) for other in kept),
        default=0.0,
    )


def greedy_mmr(
    hits: Sequence[ScoredMemory],
    k: int,
    marginal: Callable[[ScoredMemory, Sequence[ScoredMemory]], float],
) -> tuple[RankedMemory, ...]:
    """Greedily keep the ``k`` hits of highest marginal score, recomputed against what is kept."""
    remaining = list(hits)
    kept: list[ScoredMemory] = []
    ranked: list[RankedMemory] = []
    while remaining and len(kept) < k:
        best = max(remaining, key=lambda hit: marginal(hit, kept))
        ranked.append(RankedMemory(hit=best, key=marginal(best, kept)))
        kept.append(best)
        remaining.remove(best)
    return tuple(ranked)
