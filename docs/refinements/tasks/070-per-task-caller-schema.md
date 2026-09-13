# Per-task caller-supplied schema

**Status:** open, dead until a consumer
**Area:** untrusted-content
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)
**Trigger:** a structured subagent-result feature, which is the only thing this is revisited for.
**Verified:** 2026-09-13

It was recorded inside the grammar-constrained subagent output entry, in its list of what remains
behind the same seam (ADR-0028 deferred). The fragment, verbatim: a per-task caller-supplied
schema (rejected for now, revisited only for a structured subagent-result feature).

## Trail

- 2026-09-13: Re-derived, and the trigger has not fired. There is no structured subagent-result
  feature to revisit this for: the spawn tool advertises `instruction`, `context` and, where the
  roster offers a choice, `model`
  ([spawn_spec.py](../../../brain/packages/core/src/cortex_core/spawn_spec.py)), with no slot in
  which a caller could state a result shape, and the attempt sends the fixed `REPLY_ENVELOPE` or no
  schema at all
  ([subagent_attempt.py](../../../brain/packages/core/src/cortex_core/subagent_attempt.py)). The
  origin's answer-rate addendum has since re-read the rejection and given it a second reason: the
  field names in a schema never reach the model on this engine, so a richer per-task schema would
  buy constraint and explain nothing. That reasoning survives the 2026-09-13 wording change, which
  moved the sentence the model does read and left the schema where it was.
