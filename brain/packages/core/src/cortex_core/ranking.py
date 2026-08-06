"""What a ``RecallPolicy`` returns: the hits it kept, the key it ranked them by, and what that
key means (ADR-0038).

v1 ``select`` returned a bare sequence of hits, which said *which* memories a turn saw and never
*why*. ADR-0008's relevance-field addendum declined to answer that with a second field on
``ScoredMemory``, because the store's score has exactly one meaning (the raw cosine) and the
policies rank by three different quantities, one of them incomparable between hits. This module is
the answer it pointed at instead: the policy's own quantity lives on the policy's own return type,
carried with a named basis that says what the number is and whether two of them may be compared.
Pure data, no I/O; ``RecallAudit`` is the value the ``RecallAuditSink`` port records.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from cortex_core.memory import ScoredMemory


class RankBasis(Enum):
    """How a memory came to mind: the quantity a policy ordered by (ADR-0038 decision 4).

    One word per policy, and the family's split is the finding it exists to carry. ``ECHO`` is the
    store's raw cosine, likeness and nothing else. ``EMBER`` is that likeness still warm, the
    similarity-and-recency blend. ``SPREAD`` is likeness less what is already said, the MMR
    objective over raw similarity, and ``SWEEP`` is Ember spread out, that same objective over the
    blend. ``VERDICT`` is the model's own placing of the candidates.

    ``comparable`` is the load-bearing part: an MMR objective is computed against the kept set at
    pick time, so two ``SPREAD`` or ``SWEEP`` keys in one result were measured against different
    sets and mean nothing next to each other, while ``ECHO``, ``EMBER`` and ``VERDICT`` keys are
    per-hit quantities that do compare. A consumer that thresholds or plots a key must read this
    first.
    """

    ECHO = "echo"
    EMBER = "ember"
    SPREAD = "spread"
    SWEEP = "sweep"
    VERDICT = "verdict"

    @property
    def comparable(self) -> bool:
        """Whether two keys on this basis may be compared within one result."""
        return self not in _ORDER_DEPENDENT


# The bases whose key depends on what was already kept when the hit was picked.
_ORDER_DEPENDENT = frozenset({RankBasis.SPREAD, RankBasis.SWEEP})


@dataclass(frozen=True, slots=True)
class RankedMemory:
    """One kept hit, paired with the key its policy actually ordered by.

    ``hit.score`` stays the store's raw cosine, unchanged and still meaning exactly that; ``key`` is
    the policy's quantity, whose meaning is the ranking's ``basis``. Higher is better for every
    basis, so a ranking's hits are in descending ``key`` order by construction.
    """

    hit: ScoredMemory
    key: float


@dataclass(frozen=True, slots=True)
class Ranking:
    """A policy's answer: the hits it kept, in order, and the basis its keys are on.

    The basis rides the ranking rather than each hit because one ``select`` call ranks by exactly
    one quantity. An empty ranking still carries a basis: which policy declined to return anything
    is worth knowing.
    """

    hits: tuple[RankedMemory, ...]
    basis: RankBasis

    @property
    def memories(self) -> tuple[ScoredMemory, ...]:
        """The kept hits without their keys, for a caller that only wants the memories."""
        return tuple(ranked.hit for ranked in self.hits)


@dataclass(frozen=True, slots=True)
class RecallAudit:
    """One recall as its trail sees it: what was asked, how wide the pool was, and what ranked.

    ``query`` is the user's text and ``ranking`` carries the recalled memories, so both are
    conversation content: a sink that writes anywhere durable is responsible for what it keeps of
    them, and the shipped ``LoggingRecallSink`` keeps neither (ADR-0038 decision 5). ``pool_size``
    is how many candidates the store returned for the policy to choose from, which together with
    ``len(ranking.hits)`` is what makes "why these?" answerable at all.
    """

    session_id: str
    query: str
    pool_size: int
    k: int
    ranking: Ranking
    at: datetime
