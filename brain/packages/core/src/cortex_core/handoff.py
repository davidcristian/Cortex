"""The brain-handoff record: the mid-turn state a model swap must not lose (ADR-0030).

Per the one hard rule, the record carries ONLY what is not already in a store when the cortex
escalates mid-turn: the escalation brief, the turn's fence nonce, the serialized ``TaintLedger``
(both bits, sources, laundering-evidence URLs), the turn-wide dispatch-budget position, and the
tool loop's never-persisted tail (the assistant tool-call messages and their fenced ``Role.TOOL``
results, in order). Everything else (history, tasks, schedules, memories) already survives in
its own store. The tail is text-only by the same invariant the session stores enforce
(ADR-0029): ``Message`` carries no pixels today, and the day it can, the handoff record refuses
image-bearing messages the way those stores do rather than quietly widening pixel persistence.

``EscalationSlot`` is how the in-flight state reaches the serializer. Whoever orchestrates the
turn (the escalating engine wrapper, ADR-0030 decision 5) builds the empty slot before the turn
exists; the engine **arms** it at turn start by filling ``refs`` (an ``EscalationRefs`` holding
references to the live ``working`` list, ledger, nonce, and budget, created next to the ledger
and nonce); the ``escalate_to_brain`` tool writes only ``brief``; the conductor snapshots
everything else at the loop boundary, after the cortex phase's generator has finished, so
nothing is copied mid-flight. Pure data and pure functions, no I/O.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from cortex_core.conversation import Message, Role
from cortex_core.provenance import Provenance
from cortex_core.tool_budget import DispatchBudget
from cortex_core.untrusted import TaintLedger


class HandoffState(Enum):
    """Where one handoff stands: ``PENDING`` → ``READY`` → ``BRAIN_ACTIVE`` → ``DONE``/``FAILED``.

    The two terminal states are the only ones boot recovery leaves alone: any non-terminal
    record found at startup is a handoff a crash interrupted, marked ``FAILED`` (ADR-0030
    decision 4). ``terminal`` is the store-facing distinction (a terminal record stops being
    ``active()`` and may expire); the full transition sequence is the conductor's, not a store's.
    """

    PENDING = "pending"
    READY = "ready"
    BRAIN_ACTIVE = "brain_active"
    DONE = "done"
    FAILED = "failed"

    @property
    def terminal(self) -> bool:
        """Whether this state ends the handoff (nothing will transition it further)."""
        return self in _TERMINAL_STATES


# The states after which a record is history rather than an in-flight handoff. Held beside the
# enum (the `SourceKind.attested` precedent) so the members keep their wire-ish string values.
_TERMINAL_STATES = frozenset({HandoffState.DONE, HandoffState.FAILED})


@dataclass(frozen=True, slots=True)
class HandoffRecord:
    """One serialized escalation: the turn state that must survive the model swap (ADR-0030).

    ``handoff_id`` is the escalating ``turn_id`` (one handoff per turn at most);
    ``requested_at`` must be timezone-aware, since the record outlives the process that wrote
    it. ``brief`` is the cortex-authored statement of what the deep model should do (model
    text, the conversation's own trust domain). ``nonce`` is the turn's fence id, carried so
    the fenced blocks in ``loop_tail`` stay explained by the preamble's markers-carry-a-random-
    id rule instead of becoming unexplained markers under a fresh nonce. ``tainted`` /
    ``opaque`` / ``sources`` / ``untrusted_urls`` are the whole ``TaintLedger``
    (ADR-0013/0015/0027/0029): taint that did not survive the swap would fail open, and without
    the URL set the brain phase's guardrail would forget every URL read before the swap.
    ``opaque`` is carried as **defence in depth** and nothing else: no opaque turn produces a
    record today, because ``SwapConductor._prepare`` refuses one before it snapshots, so every
    record written now says ``False`` truthfully. What the schema must not do is *invent* that
    ``False``, because both consumers of the bit open on it after the swap (the default URL
    guardrail stops scanning strictly, and an opaque turn stops being kept out of durable
    memory), so a bit that decayed in transit would fail open the day anything relaxes that
    refusal. ``budget_remaining`` / ``budget_closed`` carry the turn-wide dispatch pool's
    position, so a swap can never refill the turn's allowance. ``rounds_used`` counts the
    tool-loop rounds that dispatched (one assistant tool-call message each), and ``loop_tail``
    is every message the loop appended this turn, in order. Tool-call stamps are transient live
    handles and are never persisted (``tools.py``: the loop persists the unstamped calls), so a
    re-read tail carries ``UNSTAMPED`` calls, exactly as it was appended.
    """

    handoff_id: str
    session_id: str
    requested_at: datetime
    state: HandoffState
    brief: str
    nonce: str
    tainted: bool
    opaque: bool
    sources: tuple[Provenance, ...]
    untrusted_urls: frozenset[str]
    budget_remaining: int
    budget_closed: bool
    rounds_used: int
    loop_tail: tuple[Message, ...]

    def __post_init__(self) -> None:
        if self.requested_at.tzinfo is None or self.requested_at.utcoffset() is None:
            msg = "HandoffRecord.requested_at must be timezone-aware"
            raise ValueError(msg)

    def taint_ledger(self) -> TaintLedger:
        """Reconstruct the turn's ``TaintLedger`` for the brain phase (ADR-0030 decision 4).

        An exact rebuild of everything the record carries: both bits, the sources in the order
        the turn read them (claimed kinds still claimed, attested still attested, since
        ``Provenance`` round-trips whole), and the full laundering-evidence URL set. The contract
        test pins this round trip through the store; losing any part of it here would fail open
        after a swap. ``opaque`` is rebuilt from the record rather than left at its default so
        the deep phase's guardrail and memory policy read the turn's own answer, not the one a
        fresh ledger happens to start with.
        """
        return TaintLedger(
            tainted=self.tainted,
            opaque=self.opaque,
            untrusted_urls=set(self.untrusted_urls),
            sources=self.sources,
        )


@dataclass(frozen=True, slots=True)
class EscalationRefs:
    """The live turn-local state the engine arms an ``EscalationSlot`` with at turn start.

    References (not copies) to the turn's ``working`` list, ``taint`` ledger, and shared
    ``budget``, plus the fence ``nonce``; ``base_len`` is how many messages ``working`` held
    when the tool loop began, so everything past it is the loop's appended tail. A frozen
    bundle: the referenced objects stay live and mutable (that is the point), but which
    objects one turn armed is not revisable mid-turn.
    """

    working: list[Message]
    taint: TaintLedger
    nonce: str
    budget: DispatchBudget
    base_len: int


@dataclass(slots=True)
class EscalationSlot:
    """The turn-local handle through which in-flight state reaches the handoff serializer.

    Built empty by whoever orchestrates the turn (the escalating engine wrapper, ADR-0030
    decision 5) so it can hold the slot across the delegated turn; the engine arms ``refs``
    next to the ledger and nonce at turn start; the ``escalate_to_brain`` tool writes only
    ``brief`` (``None`` = no escalation this turn); the conductor calls ``snapshot`` at the
    loop boundary, once the cortex phase's generator has finished. Mutable and turn-local on
    purpose, like the ledger it rides beside: one slot serves exactly one turn (a fresh slot
    per turn is the builder's contract), it dies with that turn, and only its snapshot is
    persisted.
    """

    refs: EscalationRefs | None = None
    brief: str | None = None

    def snapshot(self, *, turn_id: str, session_id: str, requested_at: datetime) -> HandoffRecord:
        """Serialize the slot into a ``READY`` ``HandoffRecord`` (ADR-0030 decision 4 step 1).

        Snapshotting a slot no tool ever filled is a caller bug, so a ``None`` ``brief``
        raises rather than persisting an empty escalation; so is snapshotting a slot no
        engine ever armed. ``rounds_used`` is derived from the tail: the loop appends exactly
        one ``Role.ASSISTANT`` tool-call message per round that dispatched, and a final
        text-only round appends nothing.
        """
        if self.brief is None:
            msg = "EscalationSlot.snapshot requires a brief (no escalation was requested)"
            raise ValueError(msg)
        if self.refs is None:
            msg = "EscalationSlot.snapshot requires an armed slot (no turn ever filled refs)"
            raise ValueError(msg)
        tail = tuple(self.refs.working[self.refs.base_len :])
        if any(message.images for message in tail):
            # The same rule the session stores enforce (ADR-0029): a handoff record is durable,
            # and the record schema has no field for pixels, so accepting one would drop the
            # picture in silence and hand the deep model a caption with nothing attached. The
            # conductor refuses an opaque turn before it can reach here (that is the user-facing
            # answer), so this is the invariant behind it: an unreachable raise, like the one
            # ``Message`` makes for a persistable role, not the mechanism anything relies on.
            msg = "a handoff record never persists images: pixels are turn-local"
            raise ValueError(msg)
        return HandoffRecord(
            handoff_id=turn_id,
            session_id=session_id,
            requested_at=requested_at,
            state=HandoffState.READY,
            brief=self.brief,
            nonce=self.refs.nonce,
            tainted=self.refs.taint.tainted,
            opaque=self.refs.taint.opaque,
            sources=self.refs.taint.sources,
            untrusted_urls=frozenset(self.refs.taint.untrusted_urls),
            budget_remaining=self.refs.budget.limit - self.refs.budget.spent,
            budget_closed=self.refs.budget.closed,
            rounds_used=sum(1 for message in tail if message.role is Role.ASSISTANT),
            loop_tail=tail,
        )
