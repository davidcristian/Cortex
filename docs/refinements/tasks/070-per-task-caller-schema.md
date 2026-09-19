# Per-task caller-supplied schema

**Status:** open, waiting for a consumer
**Area:** untrusted-content
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)
**Trigger:** a structured subagent-result feature, which is the only thing this is revisited for.
**Verified:** 2026-09-19

Left behind by [R-068](068-grammar-constrained-subagent-output.md): letting the caller supply a
schema per task instead of the fixed envelope. Rejected for now and revisited only for a
structured subagent-result feature.

## History

- 2026-09-13: Checked, and the trigger has not fired. There is no structured subagent-result
  feature to revisit this for: the spawn tool advertises `instruction`, `context` and, where the
  roster offers a choice, `model`
  ([spawn_spec.py](../../../brain/packages/core/src/cortex_core/spawn_spec.py)), with no slot in
  which a caller could state a result shape, and the attempt sends the fixed `REPLY_ENVELOPE` or
  no schema at all
  ([subagent_attempt.py](../../../brain/packages/core/src/cortex_core/subagent_attempt.py)). The
  origin's answer-rate measurement has since given the rejection a second reason: the field names
  in a schema never reach the model on this engine, so a richer per-task schema would constrain
  the output and explain nothing.
- 2026-09-19: Checked again, and the trigger has not fired. `build_spawn_spec` in `spawn_spec.py`
  still gives each subtask item `instruction` and `context`, and `model` only when the spawn is
  tool-less and the roster has more than one entry, so a caller still has no slot for a result
  shape; `subagent_attempt.py` still sets `REPLY_ENVELOPE` or no schema. Neither file has changed
  since 2026-09-13, and no structured subagent-result feature has been proposed.
