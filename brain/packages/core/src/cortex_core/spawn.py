"""The ``spawn_subagents`` built-in tool: delegate subtasks concurrently (ADR-0010/0018).

The cortex calls this like any tool. Each instruction becomes a ``SubagentTask`` persisted to the
``TaskStore``; the ``SubagentRunner``s are dispatched together under the ``SubagentScheduler``'s
CPU budget, and the aggregated results feed back to the cortex. The tool is given only to the
cortex, never to a subagent, so delegation fan-out stays depth-1. Bad arguments become an
``is_error`` result the model can correct rather than an exception.

Slice 8.6 (ADR-0018): an instructions item is a bare string or ``{instruction, model?, context?}``
so the cortex picks the subagent model per subtask from the runner's roster and hands it working
material. The spec is built from that roster and is honest about the wiring: when subagents are
tools-enabled, ADR-0017 pins every spawn to the robust default, so no ``model`` knob is
advertised at all. It is also honest about the *measured* trade-off (ADR-0012 admission-wall
addendum): each roster entry keeps its one backend's lease for the whole stream, so subtasks
sharing a model serialize and only subtasks on **distinct** models overlap; the spec points the
cortex at distinct-model spread as the wall-clock lever, not a blanket parallel speedup. Each task
is stamped with the spawning turn's taint (the ``tainted`` bit of the dispatcher's ``TurnStamp``
on the call, ADR-0018/0027), which the runner's resolution needs. Enforcement itself lives in
``SubagentRoster.resolve``, not here.

One call's batch is capped at ``MAX_SPAWN_BATCH`` (ADR-0010 batch-cap addendum): the turn's
dispatch pool bounds what the batch may *reach*, never how much work it queues.
"""

import asyncio
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast
from uuid import uuid4

from cortex_core.ports import Clock, TaskStore
from cortex_core.roster import SubagentRoster
from cortex_core.runner import SubagentRunner
from cortex_core.subagents import SubagentResult, SubagentTask
from cortex_core.tools import ToolCall, ToolResult, ToolSpec, Trust

SPAWN_TOOL_NAME = "spawn_subagents"

# Upper bound on the subtasks one call may ask for (ADR-0010 batch-cap addendum). The turn's
# dispatch pool (ADR-0009 turn-wide addendum) bounds what a batch may *reach*, not how much work
# it queues: a subagent that calls no tools spends nothing from that pool while still costing an
# admission slot, a placement, and a model run, and admission *queues* rather than refuses, so an
# array of fifty was fifty inferences the turn waited on. Sized above plausible delegation (two to
# five parallel subtasks) and far below fan-out spam. The turn's total is then two deliberate
# factors rather than an open end: a spawn costs a quarter of the dispatch pool, so a turn affords
# four batches of at most this many.
MAX_SPAWN_BATCH = 8

_DESCRIPTION = (
    "Delegate one or more narrow subtasks to small subagents that return their results. "
    "Use for independent lookups or transforms; each instruction must be self-contained "
    "(subagents do not see this conversation). "
    f"At most {MAX_SPAWN_BATCH} subtasks per call."
)
# Appended for a tool-less multi-entry wiring. The inline example nudges the object form (given
# only prose a live cortex folds the pick into the instruction, ADR-0018 addendum). The parallelism
# line is the measured trade-off, not a claim (same-model 10.0 s vs 4.8 s across two backends,
# ADR-0012 admission-wall addendum): it is honest and a reason for the knob beyond a directed pick.
_CHOICE_NOTE = (
    " Each subtask may pick a 'model' by using an object item, e.g. "
    '{"instruction": "...", "model": "<roster name>"}. Subtasks on distinct models run in '
    "parallel, while subtasks that share one model run one after another (one backend each), so "
    "spread independent subtasks across models to finish the batch sooner. On a turn that has "
    "read untrusted external content the robust default model is enforced regardless of the pick."
)
# Tools-enabled or a one-entry roster: every spawn runs on the one default model (ADR-0017 rule
# 2b pins it), so no knob is advertised and, sharing one backend lease, the subtasks serialize.
_PINNED_NOTE = (
    " Every subtask runs on the deployment's default subagent model, so subtasks share its one "
    "backend and run one after another, a batch that groups independent subtasks rather than "
    "running them in parallel."
)


@dataclass(frozen=True, slots=True)
class _SpawnItem:
    """One parsed instructions item: what to do, on which model, over what material."""

    instruction: str
    model: str = ""
    context: str = ""


def _model_property(roster: SubagentRoster) -> dict[str, Any]:
    """The per-subtask ``model`` JSON-Schema property, listing every entry's trade-offs."""
    options = "; ".join(
        f"{name!r} ({roster.entries[name].description})"
        if roster.entries[name].description
        else f"{name!r}"
        for name in sorted(roster.entries)
    )
    return {
        "type": "string",
        "enum": sorted(roster.entries),
        "description": (
            f"The subagent model for this subtask; omit for the default {roster.default!r}. "
            f"Options: {options}."
        ),
    }


def _build_spec(roster: SubagentRoster, *, tools_enabled: bool) -> ToolSpec:
    """The advertised spec, built from the roster and honest about the wiring (ADR-0018)."""
    item_properties: dict[str, Any] = {
        "instruction": {"type": "string", "description": "The self-contained subtask."},
        "context": {
            "type": "string",
            "description": "Optional material the subagent works from (it sees nothing else).",
        },
    }
    with_choice = not tools_enabled and len(roster.entries) > 1
    if with_choice:
        item_properties["model"] = _model_property(roster)
    return ToolSpec(
        name=SPAWN_TOOL_NAME,
        description=_DESCRIPTION + (_CHOICE_NOTE if with_choice else _PINNED_NOTE),
        parameters={
            "type": "object",
            "properties": {
                "instructions": {
                    "type": "array",
                    "maxItems": MAX_SPAWN_BATCH,
                    "items": {
                        "anyOf": [
                            {
                                "type": "string",
                                "description": (
                                    "A bare self-contained instruction (default model, no context)."
                                ),
                            },
                            {
                                "type": "object",
                                "properties": item_properties,
                                "required": ["instruction"],
                            },
                        ]
                    },
                    "description": f"One entry per subagent, at most {MAX_SPAWN_BATCH}.",
                }
            },
            "required": ["instructions"],
        },
    )


def _uuid4_task_id() -> str:
    """Default task-id factory; injectable so tests can pin ids."""
    return str(uuid4())


_ERR_INSTRUCTION = (
    "each instruction must be a non-empty string or an object with a non-empty 'instruction'"
)
# Refused, never truncated: silently dropping subtasks would hand the cortex an aggregate that
# looks complete. An error the model can act on, so it re-delegates in batches that fit.
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
    JSON string inside the array), which would otherwise run as a *literal instruction* on the
    default model, silently dropping the pick. Only a string that parses to an object carrying
    an ``instruction`` key is diverted; anything else stays a plain instruction. Model-tolerance
    only. The diverted item goes through the same validation, and ADR-0017 enforcement is the
    runner's either way.
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
        return _build_spec(self._runner.roster, tools_enabled=self._runner.tools_enabled)

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Persist each subtask, run the subagents concurrently, and aggregate their results.

        Each task carries the requested model and the spawning turn's taint (the dispatcher's
        stamp on ``call``) so the runner resolves it safely from the store alone (ADR-0018);
        the same stamp carries the turn's dispatch budget, which every spawned run shares.
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
            )
            for item in parsed
        ]
        for task in tasks:
            await self._store.put_task(task)
        # Every subagent draws from the spawning turn's dispatch pool, carried on the stamp
        # (ADR-0009 turn-wide addendum): a batch shares one allowance instead of each member
        # starting a fresh one, so an unbounded `instructions` array can no longer buy an
        # unbounded number of external calls. First come first served across the batch, which
        # is safe under `gather` because charging never awaits.
        results: list[SubagentResult] = list(
            await asyncio.gather(
                *(self._runner.run(task.id, budget=call.stamp.budget) for task in tasks)
            )
        )
        trust = Trust.UNTRUSTED if any(r.tainted for r in results) else Trust.TRUSTED
        return ToolResult(call_id=call.id, content=_format(results), trust=trust)
