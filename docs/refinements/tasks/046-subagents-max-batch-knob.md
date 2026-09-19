# A `CORTEX_SUBAGENTS_MAX_BATCH` setting

**Status:** declined 2026-08-18
**Area:** tools-mcp
**Origin:** [ADR-0010](../../adr/ADR-0010-subagents.md)

Recorded inside [R-045](045-spawn-subagents-batch-cap.md) as a setting a host could use to change
the ceiling that the batch cap ships, `MAX_SPAWN_BATCH = 8`.

Declined, because the origin decision already argued it and nothing has falsified that argument.
ADR-0010 decision 11 prefers a code constant to an environment setting, and the distinction still
holds: `CORTEX_SUBAGENTS_CPU_BUDGET` and its siblings tune what a host runs at once, which is a
deployment fact, while how many subtasks one call may ask for is policy the composition root does
not vary.

The setting would also not be free, which the entry never said. `DEFAULT_ADMISSION_WAIT_S =
3600.0` in [scheduler.py](../../../brain/packages/core/src/cortex_core/scheduler.py) is arithmetic
over this constant: its comment derives the bound from one full batch of eight against the shipped
budget, two admitted at a time, 200 to 300 s per CPU subtask, doubled to cover the serialized
placement, and [brain-core.md](../../modules/brain-core.md) repeats that derivation. A per-host
ceiling therefore invalidates a second default unless the admission wait is retuned in the same
step, and nothing enforces that pairing.

Nothing is lost by closing it. Checked again on 2026-08-18: the constant lives in
[spawn_spec.py](../../../brain/packages/core/src/cortex_core/spawn_spec.py) and reaches production
through the advertised description, the schema's `maxItems`, the array description, and the
runtime refusal in [spawn.py](../../../brain/packages/core/src/cortex_core/spawn.py). A defaulted
keyword-only parameter on `build_spawn_spec` and on `SpawnSubagentsTool.__init__` breaks none of
the existing constructions, so the day a second deployment wants a different ceiling this is an
afternoon's work, and it should be done then, against that deployment's numbers, with the
admission wait retuned beside it. This repo has one deployment, and eight was sized against it.

## History

- 2026-08-09: A review of deferred triggers ran against the tree and none fired. This is one of
  the entries whose trigger is a deployment doing something rather than a file saying something.
- 2026-08-18: Declined. The trigger is a hypothetical second host, the origin decision already
  prefers the constant, and the reading turned up a coupling the entry never mentioned: the
  default admission wait is derived from this exact number. The sibling
  [R-047](047-cost-aware-batch-cap.md) asks a different question, about the cap's unit rather than
  its value, and was read in the same pass.
