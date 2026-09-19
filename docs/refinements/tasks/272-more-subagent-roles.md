# More subagent roles

**Status:** open, optional feature
**Area:** cross-cutting
**Origin:** [ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md)
**Verified:** 2026-09-19

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
