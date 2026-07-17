"""The brain-handoff record: the mid-turn state a model swap must not lose (ADR-0030)."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from cortex_core.conversation import Message, Role
from cortex_core.provenance import Provenance
from cortex_core.tool_budget import DispatchBudget
from cortex_core.untrusted import TaintLedger


class HandoffState(Enum):
    """Where one handoff stands: ``PENDING`` → ``READY`` → ``BRAIN_ACTIVE`` → ``DONE``/``FAILED``.
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
    """One serialized escalation: the turn state that must survive the model swap (ADR-0030)."""

    handoff_id: str
    session_id: str
    requested_at: datetime
    state: HandoffState
    brief: str
    nonce: str
    tainted: bool
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
        """Reconstruct the turn's ``TaintLedger`` for the brain phase (ADR-0030 decision 4)."""
        return TaintLedger(
            tainted=self.tainted,
            untrusted_urls=set(self.untrusted_urls),
            sources=self.sources,
        )


@dataclass(slots=True)
class EscalationSlot:
    """The turn-local handle through which in-flight state reaches the handoff serializer."""

    working: list[Message]
    taint: TaintLedger
    nonce: str
    budget: DispatchBudget
    base_len: int
    brief: str | None = None

    def snapshot(self, *, turn_id: str, session_id: str, requested_at: datetime) -> HandoffRecord:
        """Serialize the slot into a ``READY`` ``HandoffRecord`` (ADR-0030 decision 4 step 1)."""
        if self.brief is None:
            msg = "EscalationSlot.snapshot requires a brief (no escalation was requested)"
            raise ValueError(msg)
        tail = tuple(self.working[self.base_len :])
        return HandoffRecord(
            handoff_id=turn_id,
            session_id=session_id,
            requested_at=requested_at,
            state=HandoffState.READY,
            brief=self.brief,
            nonce=self.nonce,
            tainted=self.taint.tainted,
            sources=self.taint.sources,
            untrusted_urls=frozenset(self.taint.untrusted_urls),
            budget_remaining=self.budget.limit - self.budget.spent,
            budget_closed=self.budget.closed,
            rounds_used=sum(1 for message in tail if message.role is Role.ASSISTANT),
            loop_tail=tail,
        )
