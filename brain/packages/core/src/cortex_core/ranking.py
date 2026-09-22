"""What a ``RecallPolicy`` returns: the kept hits, the ranking key, and what that key means."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from cortex_core.memory import ScoredMemory


class RankBasis(Enum):
    """Which quantity a policy ranked by, or why it returned nothing."""

    ECHO = "echo"
    EMBER = "ember"
    SPREAD = "spread"
    SWEEP = "sweep"
    VERDICT = "verdict"
    DEMUR = "demur"

    @property
    def comparable(self) -> bool:
        """Whether two keys on this basis may be compared within one result."""
        return self not in _ORDER_DEPENDENT


_ORDER_DEPENDENT = frozenset({RankBasis.SPREAD, RankBasis.SWEEP})


@dataclass(frozen=True, slots=True)
class RankedMemory:
    """One kept hit, paired with the key its policy actually ordered by."""

    hit: ScoredMemory
    key: float


@dataclass(frozen=True, slots=True)
class Ranking:
    """A policy's answer: the hits it kept, in order, and the basis its keys are on."""

    hits: tuple[RankedMemory, ...]
    basis: RankBasis

    def __post_init__(self) -> None:
        """Raise for the one combination that has no meaning: a declined rank that kept hits."""
        if self.basis is RankBasis.DEMUR and self.hits:
            msg = "a DEMUR ranking declines, so it has no hits"
            raise ValueError(msg)

    @property
    def memories(self) -> tuple[ScoredMemory, ...]:
        """The kept hits without their keys, for a caller that only wants the memories."""
        return tuple(ranked.hit for ranked in self.hits)


# Twenty is the shipped pool width (five recalled at a pool factor of four), so a normal
# recall lists every dropped candidate and omits none.
DROPPED_TRAIL_LIMIT = 20


@dataclass(frozen=True, slots=True)
class DroppedCandidate:
    """A candidate the store offered and the rank did not keep: its id and the store's cosine."""

    id: str
    score: float


@dataclass(frozen=True, slots=True)
class DroppedCandidates:
    """What a rank did not keep, bounded: the candidates listed, and how many more there were."""

    carried: tuple[DroppedCandidate, ...]
    omitted: int


def dropped_candidates(
    pool: Sequence[ScoredMemory], ranking: Ranking, *, limit: int = DROPPED_TRAIL_LIMIT
) -> DroppedCandidates:
    """The pool minus what ``ranking`` kept, cut to ``limit``, counting what the cut left out."""
    kept = {ranked.hit.record.id for ranked in ranking.hits}
    dropped = [hit for hit in pool if hit.record.id not in kept]
    return DroppedCandidates(
        carried=tuple(
            DroppedCandidate(id=hit.record.id, score=hit.score) for hit in dropped[:limit]
        ),
        omitted=max(len(dropped) - limit, 0),
    )


@dataclass(frozen=True, slots=True)
class RecallAudit:
    """One recall as the audit records it: the query, the pool width, and what ranked."""

    session_id: str
    turn_id: str
    query: str
    pool_size: int
    available: int
    k: int
    ranking: Ranking
    dropped: DroppedCandidates
    at: datetime
