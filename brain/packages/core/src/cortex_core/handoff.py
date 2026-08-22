"""The brain-handoff record: the mid-turn state a model swap must not lose."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from cortex_core.conversation import Message, Role
from cortex_core.provenance import Provenance
from cortex_core.tool_budget import DispatchBudget
from cortex_core.untrusted import TaintLedger


class HandoffState(Enum):
    """The stages of one handoff: PENDING, READY, BRAIN_ACTIVE, then DONE or FAILED."""

    PENDING = "pending"
    READY = "ready"
    BRAIN_ACTIVE = "brain_active"
    DONE = "done"
    FAILED = "failed"

    @property
    def terminal(self) -> bool:
        """Whether this state ends the handoff (nothing will transition it further)."""
        return self in _TERMINAL_STATES


_TERMINAL_STATES = frozenset({HandoffState.DONE, HandoffState.FAILED})


@dataclass(frozen=True, slots=True)
class HandoffRecord:
    """One serialized escalation: the turn state that must survive the model swap."""

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
    failure: str | None = None

    def __post_init__(self) -> None:
        if self.requested_at.tzinfo is None or self.requested_at.utcoffset() is None:
            msg = "HandoffRecord.requested_at must be timezone-aware"
            raise ValueError(msg)

    def taint_ledger(self) -> TaintLedger:
        """Reconstruct the turn's ``TaintLedger`` for the brain phase."""
        return TaintLedger(
            tainted=self.tainted,
            opaque=self.opaque,
            untrusted_urls=set(self.untrusted_urls),
            sources=self.sources,
        )


@dataclass(frozen=True, slots=True)
class EscalationRefs:
    """The live turn-local state the engine puts into an ``EscalationSlot`` at turn start."""

    working: list[Message]
    taint: TaintLedger
    nonce: str
    budget: DispatchBudget
    base_len: int


@dataclass(slots=True)
class EscalationSlot:
    """The turn-local handle through which in-flight state reaches the handoff serializer."""

    refs: EscalationRefs | None = None
    brief: str | None = None

    def snapshot(self, *, turn_id: str, session_id: str, requested_at: datetime) -> HandoffRecord:
        """Serialize the slot into a ``READY`` ``HandoffRecord``."""
        if self.brief is None:
            msg = "EscalationSlot.snapshot requires a brief (no escalation was requested)"
            raise ValueError(msg)
        if self.refs is None:
            msg = "EscalationSlot.snapshot requires an armed slot (no turn ever filled refs)"
            raise ValueError(msg)
        tail = tuple(self.refs.working[self.refs.base_len :])
        if any(message.images for message in tail):
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
