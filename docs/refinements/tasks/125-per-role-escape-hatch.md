# The per-role escape hatch

**Status:** open, dead until a consumer
**Area:** subagents
**Origin:** [ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md)
**Trigger:** A role needing a cheap model on a tainted or tool path for a proven-safe reason.

A future subagent role needing a cheap model on a
tainted/tool path for a proven-safe reason would be a per-role override on the same roster
seam, never a relaxation of the forced-robust default (ADR-0017 risks, ADR-0018 risks).
Unimplemented by design; no role justifies it today.

## Trail

- 2026-07-15: Extracted from the ROADMAP's deferred-refinements section into this area doc, kept
  verbatim.
- 2026-08-09: The costing pass over the feature-breadth bucket read the neighbouring "more
  subagent roles" headline against the brain and found no role concept to extend: the only `role`
  in the core is `Message.role`, the author enum at
  `brain/packages/core/src/cortex_core/conversation.py:11`, and what exists on this axis is the
  model roster at `brain/packages/core/src/cortex_core/roster.py`, whose `resolve` enforces the
  taint boundary. That pass named this entry as consistent with there being nothing to override
  yet.
