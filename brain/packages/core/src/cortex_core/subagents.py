"""Subagent value types: the delegated task, the bounds one run gets, and its result."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class SubagentTask:
    """One narrow task delegated to a subagent, persisted to the store before it runs."""

    id: str
    instruction: str
    context: str
    at: datetime
    model: str = ""
    tainted: bool = False
    session_id: str = ""
    turn_id: str = ""

    def __post_init__(self) -> None:
        if self.at.tzinfo is None or self.at.tzinfo.utcoffset(self.at) is None:
            msg = "SubagentTask.at must be timezone-aware"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class AttemptBounds:
    """How far one placed attempt at a task may go before it must stop (ADR-0005 total-cap
    addendum).
    """

    max_tokens: int | None = None
    timeout_s: float | None = None

    def __post_init__(self) -> None:
        if self.max_tokens is not None and self.max_tokens < 1:
            msg = f"AttemptBounds.max_tokens must be at least 1, got {self.max_tokens}"
            raise ValueError(msg)
        if self.timeout_s is not None and self.timeout_s <= 0:
            # Strictly positive rather than non-negative, unlike the admission wait, because the
            # two zeros would mean opposite things: a zero wait is "never queue", a policy a
            # deployment may want, while a zero deadline is "every attempt fails before it runs".
            msg = f"AttemptBounds.timeout_s must be > 0, got {self.timeout_s}"
            raise ValueError(msg)


# What an attempt built without a deployment's numbers runs under: no cap, no deadline. A shared
# frozen instance rather than a call in an argument default, the ``DEFAULT_DISPATCH_POLICY``
# precedent.
UNBOUNDED_ATTEMPT = AttemptBounds()

DEFAULT_SUBAGENT_MAX_TOKENS = 1024
DEFAULT_SUBAGENT_RUN_TIMEOUT_S = 2400.0


@dataclass(frozen=True, slots=True)
class SubagentResult:
    """A subagent's outcome, persisted for the cortex to read."""

    task_id: str
    output: str
    ok: bool = True
    detail: str = ""
    tainted: bool = False
