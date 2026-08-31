"""What a ``RecallPolicy`` returns: the kept hits, the ranking key, and what that key means.

The whole design is ADR-0038. v1 ``select`` returned a bare sequence of hits, which said which
memories a turn saw and never why. ADR-0008's relevance-field addendum declined to answer that
with a second field on
``ScoredMemory``, because the store's score has exactly one meaning (the raw cosine) and the
policies rank by three different quantities, one of them incomparable between hits. This module is
the answer it pointed at instead: the policy's own quantity lives on the policy's own return type,
carried with a named basis that says what the number is and whether two of them may be compared.
Pure data, no I/O; ``RecallAudit`` is the value the ``RecallAuditSink`` port records, and
``dropped_candidates`` is the one answer to what a rank left in the pool.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from cortex_core.memory import ScoredMemory


class RankBasis(Enum):
    """Which quantity a policy ranked by, or why it returned nothing (ADR-0038 decision 4).

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

    ``comparable`` is what a consumer thresholding or plotting a key has to read first. An MMR
    objective is computed against the kept set at pick time, so two ``SPREAD`` or ``SWEEP`` keys in
    one result were measured against different sets and mean nothing next to each other, while
    ``ECHO``, ``EMBER`` and ``VERDICT`` keys are per-hit quantities that do compare. ``DEMUR`` sits
    with the comparable bases with nothing to compare, having no key at all: nothing on it was
    measured against a kept set, which is what the property is about.
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
    say a policy both declined and returned something, which no consumer could act on, so it
    raises at construction. The converse stays legal, since a heuristic policy handed an empty
    pool returns an empty ranking on its own basis and means only that there was nothing to rank.
    """

    hits: tuple[RankedMemory, ...]
    basis: RankBasis

    def __post_init__(self) -> None:
        """Raise for the one combination that has no meaning: a declined rank that kept hits."""
        if self.basis is RankBasis.DEMUR and self.hits:
            msg = "a DEMUR ranking declines, so it carries no hits"
            raise ValueError(msg)

    @property
    def memories(self) -> tuple[ScoredMemory, ...]:
        """The kept hits without their keys, for a caller that only wants the memories."""
        return tuple(ranked.hit for ranked in self.hits)


# How many dropped candidates one recall's trail carries (ADR-0038 dropped-candidate addendum).
# The shipped shape is a pool of twenty, five recalled at a pool factor of four, so a whole pool
# fits and nothing is omitted; the bound bites only where a deployment over-fetches wider than what
# ships, and there an unbounded line would grow with the pool until the trail itself is the thing
# worth turning off. What a bound drops is the tail of the store's own order, the candidates the
# store itself rated lowest, and the line says how many it dropped rather than hiding the cut.
DROPPED_TRAIL_LIMIT = 20


@dataclass(frozen=True, slots=True)
class DroppedCandidate:
    """A candidate the store offered and the rank did not keep: its id and the store's cosine.

    ``score`` is the store's raw cosine, exactly as ``ScoredMemory.score`` means it, and there is
    deliberately no rank key beside it. A ``Ranking`` carries keys for the hits it kept and for
    nothing else, so no key for a passed-over candidate is on record anywhere: the judge omits an
    unhelpful memory from its order rather than scoring it low, and an MMR objective for an unpicked
    candidate would depend on a kept set it never joined. Two bases could compute one after the
    fact (``ECHO`` is the cosine already here, ``EMBER`` blends it with the age), but only the
    policy holds the parameters, and the policy did not. So this type says what the store offered,
    never why the rank declined it.

    Text is absent by construction rather than by a sink's restraint, because nothing an
    investigation needs from a dropped candidate is in its words: an id pairs with the store when
    the content is wanted, under whatever access reading the store already requires.
    """

    id: str
    score: float


@dataclass(frozen=True, slots=True)
class DroppedCandidates:
    """What a rank left in the pool, bounded: the candidates carried, and how many more there were.

    ``carried`` is in the pool's own order, which ``MemoryStore.search`` promises is most-similar
    first, so a bound cuts the tail and keeps the candidates the store itself rated highest.
    ``omitted`` is how many the bound left out, ``0`` whenever the whole dropped set fits. It is
    carried rather than left to arithmetic over ``pool_size`` so that no reader mistakes a
    truncated list for the complete one.
    """

    carried: tuple[DroppedCandidate, ...]
    omitted: int


def dropped_candidates(
    pool: Sequence[ScoredMemory], ranking: Ranking, *, limit: int = DROPPED_TRAIL_LIMIT
) -> DroppedCandidates:
    """The pool minus what ``ranking`` kept, bounded to ``limit``, counting what the bound left out.

    The one answer to "what did this rank leave behind", so a second consumer never derives it a
    second way. Identity is the memory id: a candidate is dropped when no kept hit carries its id.
    Membership is all this reads, so it is true of every basis, including a rank that kept nothing
    at all, where the whole pool is what was dropped.
    """
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
    """One recall as the trail records it: the query, the pool width, and what ranked.

    ``query`` is the user's text and ``ranking`` carries the recalled memories, so both are
    conversation content: a sink that writes anywhere durable is responsible for what it keeps of
    them, and the shipped ``LoggingRecallSink`` keeps neither (ADR-0038 decision 5). ``pool_size``
    is how many candidates the store returned for the policy to choose from, which together with
    ``len(ranking.hits)`` is what makes "why these?" answerable at all.

    ``dropped`` is the other half of that question and the half a count cannot answer: which
    candidates the rank passed over, by id and by the store's cosine, bounded (ADR-0038
    dropped-candidate addendum). Without it a memory that never came back is indistinguishable
    from one the store never offered, which is exactly the pair an investigation has to tell apart,
    and the ranks that drop most of the pool are the ones that ship.

    ``available`` is how many candidates the read scopes held, which is the store's own count and
    not a length over the rows it returned (ADR-0038 candidate-count addendum). It is what makes
    "never a candidate" readable: ``pool_size == available`` says the pool was the whole readable
    store, so a memory absent from the line was never written or was written outside the scopes,
    while ``pool_size < available`` says the pool was cut and an absent memory may simply have
    ranked below the cutoff. The two numbers come from two reads
    rather than one transaction, so ``available`` describes the store as of a moment beside the
    search rather than an invariant tied to ``pool_size``.
    """

    session_id: str
    query: str
    pool_size: int
    available: int
    k: int
    ranking: Ranking
    dropped: DroppedCandidates
    at: datetime
