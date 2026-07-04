"""Subagent value types: the delegated task and its result (pure data, no I/O, see ADR-0010)."""

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

    def __post_init__(self) -> None:
        if self.at.tzinfo is None or self.at.tzinfo.utcoffset(self.at) is None:
            msg = "SubagentTask.at must be timezone-aware"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class SubagentResult:
    """A subagent's outcome, persisted for the cortex to read."""

    task_id: str
    output: str
    ok: bool = True
    detail: str = ""
    tainted: bool = False
