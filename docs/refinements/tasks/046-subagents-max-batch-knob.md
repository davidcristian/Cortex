# A `CORTEX_SUBAGENTS_MAX_BATCH` knob

**Status:** declined 2026-08-18
**Area:** tools-mcp
**Origin:** [ADR-0010](../../adr/ADR-0010-subagents.md)

Recorded inside the entry for the batch cap on `spawn_subagents`, in the list of items remaining
behind the same tool:

> a **`CORTEX_SUBAGENTS_MAX_BATCH` knob** if a host ever wants a different ceiling

The ceiling it would make configurable is the one the batch cap ships: "`MAX_SPAWN_BATCH = 8` (a
constant beside `MAX_TOOL_DISPATCHES`, since how many subtasks one *call* may ask for is policy,
while what the host runs *concurrently* is the deployment fact the CPU-budget env already tunes)".

**Declined, because the origin decision already argued this and nothing has falsified it.**
ADR-0010's batch-cap addendum has a paragraph headed "why a code constant and not an env knob",
and its distinction still holds: `CORTEX_SUBAGENTS_CPU_BUDGET` and its siblings tune what a host
runs at once, which is a deployment fact, while how many subtasks one call may *ask* for is policy
the composition root does not vary. This entry restates that paragraph and adds a trigger for it,
and a backlog that must be empty before the finish line should not carry an entry whose whole
content is a decision already written down.

**The knob is also not free, which the entry does not say.** `DEFAULT_ADMISSION_WAIT_S = 3600.0`
in [scheduler.py](../../../brain/packages/core/src/cortex_core/scheduler.py) is arithmetic *over*
this constant: its comment derives the bound from one full batch of eight against the shipped
budget, two admitted at a time, 200 to 300 s per CPU subtask, doubled to cover the serialized
placement, and [brain-core.md](../../modules/brain-core.md) restates that derivation. A per-host
ceiling therefore silently invalidates a second default unless the admission wait is retuned in
the same step, and nothing gates that pairing. A knob whose honest form is two knobs is worth
more thought than "a host wants a different number".

**Nothing is lost by closing it.** Re-derived 2026-08-18: the constant lives in
[spawn_spec.py](../../../brain/packages/core/src/cortex_core/spawn_spec.py) (the ADR still says
`spawn.py`, which was true until the line cap split that module) and reaches production through
the advertised description, the schema's `maxItems`, the array description, and the runtime
refusal in [spawn.py](../../../brain/packages/core/src/cortex_core/spawn.py). A defaulted
keyword-only parameter on `build_spawn_spec` and on `SpawnSubagentsTool.__init__` breaks none of
the existing constructions, so the day a second deployment genuinely wants a different ceiling
this is an afternoon, and it should be built then, against that deployment's numbers, with the
admission wait retuned beside it. This repo has one deployment, and eight was sized against it.

## Trail

- 2026-08-09: A trigger sweep of the fix-when-it-bites bucket ran against the tree and fired
  nothing. The index names the salience and batch-cap knobs among the entries whose trigger is a
  deployment doing something rather than a file saying something, so no reading of the code settles
  them.
- 2026-08-18: Declined on a re-derivation of the tree. The trigger is a hypothetical second host,
  the origin decision already argues the constant over the knob, and the read turned up a coupling
  the entry never mentioned: the default admission wait is derived from this exact number. The
  sibling cost-aware batch cap ([047](047-cost-aware-batch-cap.md)) asks a different question, about
  the cap's unit rather than its value, and was read in the same pass on its own reasoning. The
  correction about where the constant now lives is recorded in the origin decision's addendum.
