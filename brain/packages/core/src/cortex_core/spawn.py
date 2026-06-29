"""The ``spawn_subagents`` built-in tool: delegate subtasks concurrently (ADR-0010).

The cortex calls this like any tool. Each instruction becomes a ``SubagentTask`` persisted to the
``TaskStore``; the ``SubagentRunner``s run **concurrently**, bounded by the ``SubagentScheduler``'s
CPU budget; the aggregated results feed back to the cortex. A batch (not one-per-call) is what
makes the concurrency budget meaningful. The tool is given only to the cortex, never to a
subagent, so delegation fan-out stays depth-1. Bad arguments become an ``is_error`` result the
model can correct rather than an exception.
"""

import asyncio
from collections.abc import Callable, Mapping, Sequence
from typing import Any, cast
from uuid import uuid4

from cortex_core.ports import Clock, TaskStore
from cortex_core.runner import SubagentRunner
from cortex_core.subagents import SubagentResult, SubagentTask
from cortex_core.tools import ToolCall, ToolResult, ToolSpec

SPAWN_TOOL_NAME = "spawn_subagents"

_SPEC = ToolSpec(
    name=SPAWN_TOOL_NAME,
    description=(
        "Delegate one or more narrow subtasks to small subagents that run concurrently and "
        "return their results. Use for independent lookups or transforms worth parallelizing; "
        "each instruction must be self-contained (subagents do not see this conversation)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "instructions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "One self-contained instruction per subagent.",
            }
        },
        "required": ["instructions"],
    },
)


def _uuid4_task_id() -> str:
    """Default task-id factory; injectable so tests can pin ids."""
    return str(uuid4())


def _parse_instructions(arguments: Mapping[str, Any]) -> list[str] | str:
    """Validate the ``instructions`` argument; return the list or an error message string."""
    raw = arguments.get("instructions")
    if not isinstance(raw, list) or not raw:
        return "spawn_subagents requires a non-empty 'instructions' array"
    instructions: list[str] = []
    for item in cast("list[object]", raw):
        if not isinstance(item, str) or not item.strip():
            return "each instruction must be a non-empty string"
        instructions.append(item)
    return instructions


def _format(results: Sequence[SubagentResult]) -> str:
    """Aggregate subagent outcomes into one readable block, one section per subagent."""
    lines = [
        f"[subagent {i}] {r.output if r.ok else f'FAILED: {r.detail}'}"
        for i, r in enumerate(results, start=1)
    ]
    return "\n\n".join(lines)


class SpawnSubagentsTool:
    """Built-in ``spawn_subagents`` tool over a ``SubagentRunner`` + ``TaskStore`` (ADR-0010)."""

    def __init__(
        self,
        runner: SubagentRunner,
        store: TaskStore,
        clock: Clock,
        *,
        task_id_factory: Callable[[], str] = _uuid4_task_id,
    ) -> None:
        self._runner = runner
        self._store = store
        self._clock = clock
        self._task_id_factory = task_id_factory

    @property
    def spec(self) -> ToolSpec:
        """The tool advertised to the cortex."""
        return _SPEC

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Persist each subtask, run the subagents concurrently, and aggregate their results."""
        parsed = _parse_instructions(call.arguments)
        if isinstance(parsed, str):
            return ToolResult(call_id=call.id, content=parsed, is_error=True)
        tasks = [
            SubagentTask(
                id=self._task_id_factory(), instruction=text, context="", at=self._clock.now()
            )
            for text in parsed
        ]
        for task in tasks:
            await self._store.put_task(task)
        results: list[SubagentResult] = list(
            await asyncio.gather(*(self._runner.run(task.id) for task in tasks))
        )
        return ToolResult(call_id=call.id, content=_format(results))
