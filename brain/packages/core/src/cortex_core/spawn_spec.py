"""The advertised ``spawn_subagents`` tool spec, built from the runner's roster (ADR-0010/0018).

Split from ``spawn.py`` at the 300-line cap; the contract is the same. This module owns what the
cortex is told about delegation (the tool name, the per-call batch cap, and the JSON-Schema and
prose description), and ``spawn.py`` owns what running one does.

Under ADR-0018 an instructions item is a bare string or ``{instruction, model?, context?}``, so the
cortex picks the subagent model per subtask from the roster and hands it working material. The spec
matches the wiring: when subagents are tools-enabled, ADR-0017 pins every spawn to the robust
default, so no ``model`` knob is advertised at all. It is also deliberately conservative about
parallelism rather than making a blanket claim (ADR-0012 bounded-admission-wait addendum): an entry
holds a backend per placement target and each keeps its lease for the whole stream, so subtasks
sharing a model overlap at most two ways, the admitted pair, where the advertised text says they
run one after another. That understatement is measured and left standing on purpose (ADR-0018
declined the rewrite, its task open in ``docs/refinements/index.md#subagents``): it points the
cortex at distinct-model spread as the wall-clock lever, and one deployment's behaviour does not
say which new wording would be taken.

One call's batch is capped at ``MAX_SPAWN_BATCH`` (ADR-0010 batch-cap addendum), advertised as the
array's ``maxItems`` and in prose; the runtime check in ``spawn.py`` is the backstop.
"""

from typing import Any

from cortex_core.roster import SubagentRoster
from cortex_core.tools import ToolSpec

SPAWN_TOOL_NAME = "spawn_subagents"

# Upper bound on the subtasks one call may ask for (ADR-0010 batch-cap addendum). The turn's
# dispatch pool (ADR-0009 turn-wide addendum) bounds what a batch may reach rather than how much
# work it queues: a subagent that calls no tools spends nothing from that pool while still costing
# an admission slot, a placement, and a model run, and admission queues rather than refuses, so an
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
# line understates the shipped case rather than overselling it (same-model spawns overlap at most
# two ways, 10.0 s vs 4.8 s across two backends, ADR-0012 bounded-admission-wait addendum): the
# conservative wording stands on purpose, still a reason for the knob beyond a directed pick.
_CHOICE_NOTE = (
    " Each subtask may pick a 'model' by using an object item, e.g. "
    '{"instruction": "...", "model": "<roster name>"}. Subtasks on distinct models run in '
    "parallel, while subtasks that share one model run one after another (one backend each), so "
    "spread independent subtasks across models to finish the batch sooner. On a turn that has "
    "read untrusted external content the robust default model is enforced regardless of the pick."
)
# Tools-enabled or a one-entry roster: every spawn runs on the one default model (ADR-0017 rule
# 2b pins it), so no knob is advertised and the batch has no spread left to reach for. The note
# carries the same conservative wording as the choice note above, understating the admitted pair's
# two-way overlap rather than promising a speedup this wiring cannot give.
_PINNED_NOTE = (
    " Every subtask runs on the deployment's default subagent model, so subtasks share its one "
    "backend and run one after another, a batch that groups independent subtasks rather than "
    "running them in parallel."
)


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


def build_spawn_spec(roster: SubagentRoster, *, tools_enabled: bool) -> ToolSpec:
    """The advertised spec, built from the roster and matching the wiring (ADR-0018)."""
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
