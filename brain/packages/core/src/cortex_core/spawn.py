"""The ``spawn_subagents`` built-in tool: delegate subtasks concurrently (ADR-0010/0018).

The cortex calls this like any tool. Each instruction becomes a ``SubagentTask`` persisted to the
``TaskStore``; the ``SubagentRunner``s are dispatched together under the ``SubagentScheduler``'s
CPU budget, and the aggregated results feed back to the cortex. The tool is given only to the
cortex, never to a subagent, so delegation fan-out stays depth-1. Bad arguments become an
``is_error`` result the model can correct rather than an exception. Each task is stamped with the
spawning turn's taint (the ``tainted`` bit of the dispatcher's ``TurnStamp`` on the call,
ADR-0018/0027), which the runner's resolution needs; enforcement itself lives in
``SubagentRoster.resolve``, not here.

The advertised spec (what the cortex is told, including the ADR-0018 model knob and the ADR-0010
batch cap) lives in ``spawn_spec.py``; this module owns running one batch. A delegating turn also
surfaces progress (ADR-0010 progress addendum): the batch's scale as a ``StatusUpdate`` and each
subagent's audited tool steps as ``ToolActivity``, off the stream's ``ProgressSink`` carried on the
call ``TurnStamp`` (``None`` for an overlay-less caller, e.g. the ticker), so the one shared tool
serves every stream without a per-stream field.
"""

import asyncio
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast
from uuid import uuid4

from cortex_core.events import StatusUpdate
from cortex_core.ports import Clock, TaskStore
from cortex_core.roster import SubagentRoster
from cortex_core.runner import SubagentRunner
from cortex_core.spawn_spec import MAX_SPAWN_BATCH, build_spawn_spec
from cortex_core.subagents import SubagentResult, SubagentTask
from cortex_core.tools import ToolCall, ToolResult, ToolSpec, Trust

# The ``StatusUpdate.state`` a delegating turn surfaces (ADR-0010 progress addendum). Not
# ``"thinking"`` (which the overlay folds into a reasoning trace, ADR-0020), so it drives the
# live chip and nothing else. The detail is a brain-authored count, never model or subagent
# text, so it needs no guardrail pass, exactly as the ``ToolActivity`` chip does not.
SUBAGENT_PROGRESS_STATE = "delegating"


@dataclass(frozen=True, slots=True)
class _SpawnItem:
    """One parsed instructions item: what to do, on which model, over what material."""

    instruction: str
    model: str = ""
    context: str = ""


def _uuid4_task_id() -> str:
    """Default task-id factory; injectable so tests can pin ids."""
    return str(uuid4())


_ERR_INSTRUCTION = (
    "each instruction must be a non-empty string or an object with a non-empty 'instruction'"
)
# Refused rather than truncated: dropping subtasks without saying so would hand the cortex an
# aggregate that looks complete. An error the model can act on, so it re-delegates in batches
# that fit.
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
    """An object item the model JSON-encoded into the string slot, or None (ADR-0018 addendum).

    Live gemma-4-12B emits `"{\\"instruction\\": ..., \\"model\\": ...}"` (the object form as a
    JSON string inside the array), which would otherwise run as a literal instruction on the
    default model and drop the pick with nothing reporting it. Only a string that parses to an
    object carrying an ``instruction`` key is diverted; anything else stays a plain instruction.
    Model-tolerance only. The diverted item goes through the same validation, and ADR-0017
    enforcement is the runner's either way.
    """
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
    # Ahead of parsing the items, so an oversized array is refused without walking it and
    # before a single task is stored or a single subagent placed.
    if len(elements) > MAX_SPAWN_BATCH:
        return _ERR_BATCH
    items: list[_SpawnItem] = []
    for element in elements:
        parsed = _parse_item(element, roster)
        if isinstance(parsed, str):
            return parsed
        items.append(parsed)
    return items


def _progress_detail(count: int) -> str:
    """The brain-authored batch-start line: how many subtasks, no model or subagent text."""
    return f"delegating {count} subtask{'' if count == 1 else 's'}"


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
        """The tool advertised to the cortex, derived from the runner it fronts (ADR-0018)."""
        return build_spawn_spec(self._runner.roster, tools_enabled=self._runner.tools_enabled)

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Persist each subtask, run the subagents concurrently, and aggregate their results.

        Each task carries the requested model, the spawning turn's taint, and the work the spawn
        was made for (its chat, its turn id, and the scheduled item whose fire made it, each
        ``""`` when this caller has none: a turn names no item, the ticker names no turn), all
        five read from the dispatcher's stamp on ``call``, so the runner resolves it safely and
        audits it accurately from the store alone (ADR-0018, ADR-0009 named-work and fired-work
        addenda). The same stamp carries the turn's dispatch budget, which every spawned run
        shares, and the stream's ``progress`` sink (``None`` off an overlay-less caller, e.g. the
        ticker), which the batch's scale and each subagent's tool steps surface onto (ADR-0010
        progress addendum). The sink rides the stamp per call rather than an instance field, so
        this one shared tool serves every stream without a per-stream slot to leak across turns.
        The aggregate is UNTRUSTED iff any subagent consumed untrusted content, so a subagent
        that read a malicious file taints the cortex turn through the normal result path
        (ADR-0013); a bad-arguments error is our own message and stays trusted.
        """
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
        progress = call.stamp.progress
        if progress is not None:
            # The batch's scale, brain-authored: the user learns delegation is running and to how
            # many subtasks. Phrased without a parallelism claim the wiring does not deliver (a
            # batch's same-model spawns overlap at most two ways, the admitted pair, ADR-0012
            # bounded-admission-wait addendum).
            await progress.emit(
                StatusUpdate(state=SUBAGENT_PROGRESS_STATE, detail=_progress_detail(len(tasks)))
            )
        # Every subagent draws from the spawning turn's dispatch pool, carried on the stamp
        # (ADR-0009 turn-wide addendum): a batch shares one allowance instead of each member
        # starting a fresh one, so an unbounded `instructions` array can no longer buy an
        # unbounded number of external calls. First come first served across the batch, which
        # is safe under `gather` because charging never awaits. Each run is also handed the same
        # progress sink, so its own tool steps surface as they run (ADR-0010 progress addendum).
        results: list[SubagentResult] = list(
            await asyncio.gather(
                *(
                    self._runner.run(task.id, budget=call.stamp.budget, progress=progress)
                    for task in tasks
                )
            )
        )
        trust = Trust.UNTRUSTED if any(r.tainted for r in results) else Trust.TRUSTED
        return ToolResult(call_id=call.id, content=_format(results), trust=trust)
