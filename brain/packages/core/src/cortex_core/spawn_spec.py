"""The advertised ``spawn_subagents`` tool spec, built from the runner's roster (ADR-0010/0018)."""

from typing import Any

from cortex_core.roster import SubagentRoster
from cortex_core.tools import ToolSpec

SPAWN_TOOL_NAME = "spawn_subagents"

MAX_SPAWN_BATCH = 8

_DESCRIPTION = (
    "Delegate one or more narrow subtasks to small subagents that return their results. "
    "Use for independent lookups or transforms; each instruction must be self-contained "
    "(subagents do not see this conversation). "
    f"At most {MAX_SPAWN_BATCH} subtasks per call."
)
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
