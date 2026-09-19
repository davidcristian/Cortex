# More subagent roles

**Status:** open, feature breadth
**Area:** cross-cutting
**Origin:** [ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md)
**Verified:** 2026-09-19

More subagent roles.

That fragment was recorded inside the area's one grouped entry, "Cross-cutting (originally 'Later,
unordered')", which lists it beside pointer-input injection, richer memory policies and macOS/Linux
OS backends and never gave it a bullet of its own.

The fragment came from that list rather than from a decision record, which is why this entry read
`Origin: none` until 2026-09-13. The record that owns the axis a role would extend is the
heterogeneous-subagents decision: it chose the model roster as the per-subtask axis, and its own
deferred list ends with the per-role escape hatch, which is [R-125](125-per-role-escape-hatch.md)
and is the entry downstream of this one. A reader following the origin field now arrives where the
design lives, and the catch-all list the fragment was extracted from is named in the trail below.

## Trail

- 2026-07-15: Extracted from the ROADMAP's deferred-refinements section as the last clause of the
  "Later, unordered" list, and carried in the index's feature-breadth bucket as "More subagent
  roles".
- 2026-08-09: A costing pass over that bucket found this is not the cheap entry its one line
  suggests, being a bare headline with no body entry at all, because read against the brain there is
  no role concept to extend: the only `role` in the core is `Message.role`, the message-author enum
  `USER`/`ASSISTANT`/`SYSTEM`/`TOOL` at
  `brain/packages/core/src/cortex_core/conversation.py:11`, which is a different thing entirely, and
  the spawn tool's per-item schema is exactly `instruction`, `context` and an optional `model`
  (`spawn_spec.py:89` to 98). What exists on this axis is a model roster
  (`brain/packages/core/src/cortex_core/roster.py`), whose `resolve` at line 72 is where the taint
  boundary is enforced rather than described, so a role would be a new pure value type, a new spawn
  argument, resolution sitting beside that boundary, composition-root wiring and env config, which
  is a vertical slice and not a breadth add. The one place roles are already named,
  [subagents.md](../index.md#subagents) line 188, treats a per-role override as hypothetical and
  unimplemented by design, which is consistent with there being nothing to override yet, and nothing
  opened or closed in that pass.
- 2026-09-13: Re-derived, and the costing above holds while two of its citations have drifted. The
  message-author enum is `Role` in `brain/packages/core/src/cortex_core/conversation.py`, at line 24
  rather than the line 11 recorded then, and the spawn tool's per-item schema is still exactly
  `instruction`, `context` and an optional `model`, built by `build_spawn_spec` rather than at the
  lines named. `SubagentRoster.resolve` is still at line 72 and still the one place the taint
  boundary is enforced. Nothing in the brain has gained a role concept, so this is still a vertical
  slice: a new pure value type, a new spawn argument, resolution beside that boundary, wiring and
  env config. The origin field was moved off `none` in the same pass, for the reason written above.
- 2026-09-19: Re-derived, and none of it has been built. `Role` is still the message-author enum at
  `brain/packages/core/src/cortex_core/conversation.py:24`, `build_spawn_spec` still builds the
  per-item properties `instruction` and `context` and adds `model` only when the cortex has a
  choice, and `SubagentRoster.resolve` is still at line 72 and still the one place the taint
  boundary is enforced. The 2026-09-13 bullet said the schema had moved off the lines the
  2026-08-09 bullet named, which was wrong: every version of `spawn_spec.py` since 2026-08-09
  builds it at lines 89 to 98. No commit since the last reading touched the roster, the spawn tool
  or the runner, so the costing stands as a vertical slice.
