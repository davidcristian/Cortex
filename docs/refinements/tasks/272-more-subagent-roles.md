# More subagent roles

**Status:** done 2026-09-28
**Area:** cross-cutting
**Origin:** [ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md)

More subagent roles. The line came from the ROADMAP's old catch-all list rather than from a
decision record, which is why this entry read `Origin: none` until 2026-09-13. The record that owns
the axis a role would extend is the heterogeneous-subagents decision, which chose the model roster
as the per-subtask axis; its own deferred list ends with the per-role escape hatch, which is
[125](125-per-role-escape-hatch.md).

There is no role concept to extend, so this is a vertical slice rather than a small addition. The
only `role` in the core is `Message.role`, the message-author enum
`USER`/`ASSISTANT`/`SYSTEM`/`TOOL` in
`brain/packages/core/src/cortex_core/conversation.py`, which is a different thing, and the spawn
tool's per-item schema is exactly `instruction`, `context` and an optional `model`. What exists on
this axis is a model roster (`brain/packages/core/src/cortex_core/roster.py`), whose `resolve` is
the one place the taint boundary is enforced rather than described. A role would therefore be a new
pure value type, a new spawn argument, resolution beside that boundary, composition-root wiring and
env config. The one place roles are already named,
[subagents.md](../index.md#subagents), treats a per-role override as hypothetical and
unimplemented, which is consistent with there being nothing to override yet.

## History

- 2026-07-15: Extracted from the ROADMAP's deferred-refinements section as the last clause of the
  "Later, unordered" list.
- 2026-08-09: A costing pass found this is not the cheap entry its one line suggests, on the
  reasoning above.
- 2026-09-13: Checked again and the costing holds. The origin field was moved off `none` in the
  same pass.
- 2026-09-19: Checked again, and none of it has been built. `Role` is still the message-author enum
  at `brain/packages/core/src/cortex_core/conversation.py:24`, `build_spawn_spec` still builds the
  per-item properties `instruction` and `context` and adds `model` only when the cortex has a
  choice, and `SubagentRoster.resolve` is still at line 72 and still the one place the taint
  boundary is enforced. The 2026-09-13 note said the schema had moved off the lines the 2026-08-09
  note named, which was wrong: every version of `spawn_spec.py` since 2026-08-09 builds it at lines
  89 to 98. No commit since touched the roster, the spawn tool or the runner.
- 2026-09-28: Built. The claims above held at the start: `Role` was still only the message-author
  enum, the spawn item was `instruction`, `context` and an optional `model`, and
  `SubagentRoster.resolve` (now at `roster.py:43`) was still the one place the taint boundary runs.
  A role is now a pure core value in `brain/packages/core/src/cortex_core/roles.py`, holding a
  description the spawn spec advertises and one sentence naming the form of the reply, which the
  runner appends to the subtask. The spawn item gained `role`, the task record keeps its name, the
  runner resolves it beside the roster without passing it there, and `CORTEX_SUBAGENTS_ROLES` turns
  the three shipped roles off. The design, the fields left out and why, and the names are in
  [ADR-0072](../../adr/ADR-0072-subagent-roles.md). The names `precis`, `excerpt` and `answer` are a
  proposal for the maintainer's pick, with two alternative sets in that record, and nothing beyond
  this machine stores them yet. Filed [748](748-a-role-sentence-is-unmeasured-against-the-envelope-readings.md)
  for whether a role sentence changes delivery and
  [749](749-the-cortex-uptake-of-the-role-property-is-unmeasured.md) for whether the cortex names a
  role at all.
