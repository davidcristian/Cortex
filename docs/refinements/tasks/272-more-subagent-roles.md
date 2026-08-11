# More subagent roles

**Status:** open, feature breadth
**Area:** cross-cutting
**Origin:** none, this area is the old catch-all list and has no single origin decision record

More subagent roles.

That fragment was recorded inside the area's one grouped entry, "Cross-cutting (originally 'Later,
unordered')", which lists it beside pointer-input injection, richer memory policies and macOS/Linux
OS backends and never gave it a bullet of its own.

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
