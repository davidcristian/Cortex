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
    item_id: str = ""

    def __post_init__(self) -> None:
        if self.at.tzinfo is None or self.at.tzinfo.utcoffset(self.at) is None:
            msg = "SubagentTask.at must be timezone-aware"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class AttemptBounds:
    """How far one placed attempt at a task may go before it stops."""

    max_tokens: int | None = None
    timeout_s: float | None = None

    def __post_init__(self) -> None:
        if self.max_tokens is not None and self.max_tokens < 1:
            msg = f"AttemptBounds.max_tokens must be at least 1, got {self.max_tokens}"
            raise ValueError(msg)
        if self.timeout_s is not None and self.timeout_s <= 0:
            msg = f"AttemptBounds.timeout_s must be > 0, got {self.timeout_s}"
            raise ValueError(msg)


UNBOUNDED_ATTEMPT = AttemptBounds()

# About five times the longest reply a narrow subtask was measured writing on the shipped CPU
# tier, where a summarization answered in 199 tokens. Whether this or the deadline below stops a
# run first depends on host load; docs/readings/generation-bounds.md has the table.
DEFAULT_SUBAGENT_MAX_TOKENS = 1024
# Four times the longest whole subtask measured on that tier (623.8 s), and it must stay between
# the two bounds either side of it, the pool's 600 s stall ceiling and its 7200 s admission wait:
# one silent gap, then one whole run, then the queue for a run. `SubagentsConfig` checks both.
DEFAULT_SUBAGENT_RUN_TIMEOUT_S = 2400.0

# A GPU attempt that fails is re-run once on the CPU inside the same admission, each under a
# fresh deadline, so one task can hold its room for this many whole deadlines.
ATTEMPTS_PER_ADMISSION = 2


@dataclass(frozen=True, slots=True)
class SubagentResult:
    """A subagent's outcome, handed back to the spawning turn and persisted by task id."""

    task_id: str
    output: str
    ok: bool = True
    detail: str = ""
    tainted: bool = False
