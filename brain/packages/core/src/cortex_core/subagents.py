"""Subagent value types: the delegated task and its result (pure data, no I/O, see ADR-0010).

These live here, importing no ports, so ``ports.py`` can depend on them without a cycle
exactly as ``tools.py`` and ``memory.py`` do. A subagent is a stateless function over a
``TaskStore``: ``spawn_subagent`` writes a ``SubagentTask``, the runner reads it back by id and
writes a ``SubagentResult``, and the cortex reads the result. Nothing lives in a model process.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class SubagentTask:
    """One narrow task delegated to a subagent, persisted to the store before it runs.

    ``instruction`` is what to do; ``context`` is the material the subagent needs to work from
    the store alone (the cortex conversation is never shared, so the subagent is stateless over
    the task). ``at`` must be timezone-aware: task state outlives the process and any swap (the
    one hard rule), so a naive timestamp is ambiguous.
    """

    id: str
    instruction: str
    context: str
    at: datetime

    def __post_init__(self) -> None:
        if self.at.tzinfo is None or self.at.tzinfo.utcoffset(self.at) is None:
            msg = "SubagentTask.at must be timezone-aware"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class SubagentResult:
    """A subagent's outcome, persisted for the cortex to read.

    ``output`` is the answer text. ``ok`` is False when the subagent could not complete (e.g.
    its inference failed or the task vanished), ``detail`` carrying the reason. This mirrors
    ``ToolResult.is_error`` so a failed delegation is a value the cortex consumes, not a crash.
    """

    task_id: str
    output: str
    ok: bool = True
    detail: str = ""
