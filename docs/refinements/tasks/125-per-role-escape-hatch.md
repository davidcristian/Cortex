# The per-role escape hatch

**Status:** open, waiting for a consumer
**Area:** subagents
**Origin:** [ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md)
**Trigger:** A role needing a cheap model on a tainted or tool path for a proven-safe reason, which cannot happen before R-272 gives the brain a role concept: `SubagentRoster.resolve` takes no role and the spawn tool's items have none.
**Verified:** 2026-09-19

If some future subagent role needed a cheap model on a tainted or tool path for a reason proven
safe, it would be a per-role override on the same roster port, never a relaxation of the default
that forces the safest model (ADR-0017 risks, ADR-0018 risks). Nothing justifies one today.

## History

- 2026-07-15: Extracted from the ROADMAP's deferred-refinements section into this area.
- 2026-08-09: The costing pass over the feature-breadth bucket read the neighbouring "more
  subagent roles" headline against the brain and found no role concept to extend: the only `role`
  in the core is `Message.role`, the author enum at
  `brain/packages/core/src/cortex_core/conversation.py:11`, and what exists on this axis is the
  model roster at `brain/packages/core/src/cortex_core/roster.py`, whose `resolve` applies the
  taint boundary.
- 2026-09-13: Checked again; not fired. `SubagentRoster.resolve` is the whole boundary and takes
  no override: a spawn whose turn was tainted, or whose subagent is tools-enabled and can fetch
  untrusted content itself, resolves to the safest entry, `default`, whatever was requested, unknown names
  included. There is also nothing to override for, the spawn tool's per-item schema being
  `instruction`, `context` and an optional `model`, so this entry cannot fire before
  [R-272](272-more-subagent-roles.md) exists.
- 2026-09-19: Checked again; not fired. `SubagentRoster.resolve` is still at `roster.py:72` and
  still returns the `default` for any tainted or tools-enabled spawn before it reads the request,
  the spawn tool's per-item properties are unchanged, and no module in the brain has gained a role.
  The trigger now names R-272 on its own line, because a trigger read from the index gave no sign
  that it could not fire yet. R-272 waits on nothing, being an optional feature, so the two do not
  wait on each other.
