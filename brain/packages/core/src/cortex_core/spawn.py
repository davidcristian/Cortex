"""The ``spawn_subagents`` built-in tool: delegate subtasks concurrently."""

import asyncio
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast
from uuid import uuid4

from cortex_core.delegation_wait import DelegationBoard, batch_wait
from cortex_core.ports import Clock, TaskStore
from cortex_core.roster import SubagentRoster
from cortex_core.runner import SubagentRunner
from cortex_core.spawn_spec import MAX_SPAWN_BATCH, build_spawn_spec
from cortex_core.subagents import SubagentResult, SubagentTask
from cortex_core.tools import ToolCall, ToolResult, ToolSpec, Trust, TurnStamp
from cortex_core.waits import DELEGATING

SUBAGENT_PROGRESS_STATE = DELEGATING


@dataclass(frozen=True, slots=True)
class _SpawnItem:
    """One parsed instructions item: what to do, on which model, over what material."""

    instruction: str
    model: str = ""
    context: str = ""


def _uuid4_task_id() -> str:
    """Default task-id factory; injectable so tests can use fixed ids."""
    return str(uuid4())


_ERR_INSTRUCTION = (
    "each instruction must be a non-empty string or an object with a non-empty 'instruction'"
)
_ERR_BATCH = (
    f"spawn_subagents takes at most {MAX_SPAWN_BATCH} subtasks per call; delegate fewer at once"
)


def _parse_item(item: object, roster: SubagentRoster) -> _SpawnItem | str:
    """Validate one instructions item; return the parsed item or an error message string."""
    if isinstance(item, str):
        stringified = _stringified_object_item(item)
        if stringified is not None:
            return _parse_object_item(stringified, roster)
        return _SpawnItem(instruction=item) if item.strip() else _ERR_INSTRUCTION
    if not isinstance(item, Mapping):
        return _ERR_INSTRUCTION
    return _parse_object_item(cast("Mapping[str, object]", item), roster)


def _stringified_object_item(item: str) -> Mapping[str, object] | None:
    """An object item the model JSON-encoded into the string slot, or None."""
    if not item.lstrip().startswith("{"):
        return None
    try:
        parsed: object = json.loads(item)
    except ValueError:
        return None
    if isinstance(parsed, Mapping) and "instruction" in cast("Mapping[str, object]", parsed):
        return cast("Mapping[str, object]", parsed)
    return None


def _parse_object_item(entry: Mapping[str, object], roster: SubagentRoster) -> _SpawnItem | str:
    """Validate one ``{instruction, model?, context?}`` item against the roster."""
    instruction = entry.get("instruction")
    if not isinstance(instruction, str) or not instruction.strip():
        return _ERR_INSTRUCTION
    model = entry.get("model", "")
    if not isinstance(model, str):
        return "the 'model' of a subtask must be a string"
    if model and model not in roster.entries:
        options = ", ".join(sorted(roster.entries))
        return f"unknown subagent model {model!r}; options: {options}"
    context = entry.get("context", "")
    if not isinstance(context, str):
        return "the 'context' of a subtask must be a string"
    return _SpawnItem(instruction=instruction, model=model, context=context)


def _parse_instructions(
    arguments: Mapping[str, Any], roster: SubagentRoster
) -> list[_SpawnItem] | str:
    """Validate the ``instructions`` argument; return the items or an error message string."""
    raw = arguments.get("instructions")
    if not isinstance(raw, list) or not raw:
        return "spawn_subagents requires a non-empty 'instructions' array"
    elements = cast("list[object]", raw)
    # Ahead of parsing the items, so an oversized array is refused before any task is stored.
    if len(elements) > MAX_SPAWN_BATCH:
        return _ERR_BATCH
    items: list[_SpawnItem] = []
    for element in elements:
        parsed = _parse_item(element, roster)
        if isinstance(parsed, str):
            return parsed
        items.append(parsed)
    return items


def _format(results: Sequence[SubagentResult]) -> str:
    """Aggregate subagent outcomes into one readable block, one section per subagent."""
    lines = [
        f"[subagent {i}] {r.output if r.ok else f'FAILED: {r.detail}'}"
        for i, r in enumerate(results, start=1)
    ]
    return "\n\n".join(lines)


class SpawnSubagentsTool:
    """Built-in ``spawn_subagents`` tool over a ``SubagentRunner`` + ``TaskStore``."""

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
        """The tool advertised to the cortex, derived from the runner it fronts."""
        return build_spawn_spec(self._runner.roster, tools_enabled=self._runner.tools_enabled)

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Persist each subtask, run the subagents concurrently, and aggregate their results."""
        parsed = _parse_instructions(call.arguments, self._runner.roster)
        if isinstance(parsed, str):
            return ToolResult(call_id=call.id, content=parsed, is_error=True, trust=Trust.TRUSTED)
        tasks = [
            SubagentTask(
                id=self._task_id_factory(),
                instruction=item.instruction,
                context=item.context,
                at=self._clock.now(),
                model=item.model,
                tainted=call.stamp.tainted,
                session_id=call.stamp.session_id,
                turn_id=call.stamp.turn_id,
                item_id=call.stamp.item_id,
            )
            for item in parsed
        ]
        for task in tasks:
            await self._store.put_task(task)
        results = await self._run_batch(tasks, call.stamp)
        trust = Trust.UNTRUSTED if any(r.tainted for r in results) else Trust.TRUSTED
        return ToolResult(call_id=call.id, content=_format(results), trust=trust)

    async def _run_batch(
        self, tasks: Sequence[SubagentTask], stamp: TurnStamp
    ) -> list[SubagentResult]:
        """Run every subtask at once, holding the batch's wait while any of them is left."""
        progress = stamp.progress
        if progress is None:
            return await self._run_all(tasks, stamp, None)
        async with progress.hold(batch_wait(len(tasks), 0)) as hold:
            return await self._run_all(tasks, stamp, DelegationBoard(hold, len(tasks)))

    async def _run_all(
        self, tasks: Sequence[SubagentTask], stamp: TurnStamp, board: DelegationBoard | None
    ) -> list[SubagentResult]:
        """Run the subtasks concurrently, in the order they were given."""
        return list(await asyncio.gather(*(self._run_one(task, stamp, board) for task in tasks)))

    async def _run_one(
        self, task: SubagentTask, stamp: TurnStamp, board: DelegationBoard | None
    ) -> SubagentResult:
        """Run one subtask, moving it across the board as it is admitted and ends."""
        if board is None:
            return await self._runner.run(task.id, budget=stamp.budget)
        place = board.subtask()
        try:
            return await self._runner.run(
                task.id, budget=stamp.budget, progress=stamp.progress, admitted=place.admitted
            )
        finally:
            await place.ended()
