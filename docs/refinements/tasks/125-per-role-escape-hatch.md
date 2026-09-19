# The per-role escape hatch

**Status:** open, dead until a consumer
**Area:** subagents
**Origin:** [ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md)
**Trigger:** A role needing a cheap model on a tainted or tool path for a proven-safe reason, which cannot happen before R-272 gives the brain a role concept: `SubagentRoster.resolve` takes no role and the spawn tool's items carry none.
**Verified:** 2026-09-19

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
- 2026-09-13: Re-derived, still unfired, and the order of the two pieces is now written down.
  `SubagentRoster.resolve` is the whole boundary and takes no override: a spawn whose turn was
  tainted, or whose subagent is tools-enabled and can fetch untrusted content itself, resolves to
  the robust `default` whatever was requested, unknown names included. There is also nothing to
  override for, the spawn tool's per-item schema being `instruction`, `context` and an optional
  `model` and no role concept existing anywhere in the brain, so this entry cannot fire before the
  work described at [R-272](272-more-subagent-roles.md) exists. The 2026-08-09 pass costed the two
  together and left that dependency unrecorded.
- 2026-09-19: Re-derived and unfired. `SubagentRoster.resolve` is still at `roster.py:72` and still
  returns the `default` for any tainted or tools-enabled spawn before it reads the request, the
  spawn tool's per-item properties are still `instruction`, `context` and the optional `model`, and
  no module in the brain has gained a role since the last reading. The trigger now says in its own
  line that it waits on R-272, which the 2026-09-13 bullet had recorded only here, because a
  trigger read on its own from the index gave no sign that it could not fire yet. R-272 waits on
  nothing, being feature breadth, so the two do not wait on each other.
