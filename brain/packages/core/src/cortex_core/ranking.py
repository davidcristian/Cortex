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
    """How a memory came to mind, or why none did (ADR-0038 decision 4, abstention addendum).

    One word per policy, and the family's split is the finding it exists to carry. ``ECHO`` is the
    store's raw cosine, likeness and nothing else. ``EMBER`` is that likeness still warm, the
    similarity-and-recency blend. ``SPREAD`` is likeness less what is already said, the MMR
    objective over raw similarity, and ``SWEEP`` is Ember spread out, that same objective over the
    blend. ``VERDICT`` is the model's own placing of the candidates.

    ``DEMUR`` is the one member that names no quantity, because there are no hits to carry one: the
    model read the pool and answered that none of the candidates helps. It is judicial like its
    sibling ``VERDICT`` on purpose, a demurrer being the finding that the material offered makes no
    case even if every word of it is granted, and it is a decision by something that can be wrong
    rather than an absence of one. That is exactly what separates it from a heuristic basis over an
    empty ranking, which says only that there was nothing to rank.

    ``comparable`` is the load-bearing part: an MMR objective is computed against the kept set at
    pick time, so two ``SPREAD`` or ``SWEEP`` keys in one result were measured against different
    sets and mean nothing next to each other, while ``ECHO``, ``EMBER`` and ``VERDICT`` keys are
    per-hit quantities that do compare. A consumer that thresholds or plots a key must read this
    first. ``DEMUR`` sits with the comparable bases vacuously, having no key to compare with
    anything: nothing on it was measured against a kept set, which is what the property is about.
    """

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
    is worth knowing, and on ``DEMUR`` the emptiness is the answer rather than a shortfall.

    That last reading is enforced rather than described: a ``DEMUR`` ranking carrying hits would
    say a policy both declined and returned something, which no consumer could act on, so it is
    refused at construction. The converse stays legal, since a heuristic policy handed an empty
    pool returns an empty ranking on its own basis and means only that there was nothing to rank.
    """

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
