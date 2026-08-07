"""What a ``RecallPolicy`` returns: the hits it kept, the key it ranked them by, and what that
key means (ADR-0038).
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from cortex_core.memory import ScoredMemory


class RankBasis(Enum):
    """How a memory came to mind, or why none did (ADR-0038 decision 4, abstention addendum)."""

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


# The bases whose key depends on what was already kept when the hit was picked.
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
        """Refuse the one combination that has no meaning: a declined rank that kept hits."""
        if self.basis is RankBasis.DEMUR and self.hits:
            msg = "a DEMUR ranking declines, so it carries no hits"
            raise ValueError(msg)

    @property
    def memories(self) -> tuple[ScoredMemory, ...]:
        """The kept hits without their keys, for a caller that only wants the memories."""
        return tuple(ranked.hit for ranked in self.hits)


@dataclass(frozen=True, slots=True)
class RecallAudit:
    """One recall as its trail sees it: what was asked, how wide the pool was, and what ranked."""

    session_id: str
    query: str
    pool_size: int
    k: int
    ranking: Ranking
    at: datetime
