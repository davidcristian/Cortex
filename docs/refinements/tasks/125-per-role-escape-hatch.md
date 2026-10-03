# The per-role escape hatch

**Status:** open, waiting for a consumer
**Area:** subagents
**Origin:** [ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md)
**Trigger:** a readings record shows a role on a tainted or tools-enabled spawn reading higher on a non-default roster entry, with the reason that entry is safe there. None does: `docs/readings/role-sentences.md` is the only roles record, and `grep -ci 'taint' docs/readings/role-sentences.md` returns 0.
**Verified:** 2026-10-03

If a subagent role ever needed a cheap model on a tainted or tool path for a reason proven safe, it
would be a per-role override inside `SubagentRoster.resolve`
([roster.py:43](../../../brain/packages/core/src/cortex_core/roster.py)), never a relaxation of the
default that forces the safest model (ADR-0017 risks, ADR-0018 risks). Nothing justifies one today.

Building one needs three changes. A `SubagentRole` holds only a description and a sentence
([roles.py:8](../../../brain/packages/core/src/cortex_core/roles.py)), so it would need a model;
`resolve` takes only `requested`, `tainted` and `tools_enabled`, and the runner calls it before it
resolves the role ([runner.py:76](../../../brain/packages/core/src/cortex_core/runner.py)); and
[ADR-0072](../../adr/ADR-0072-subagent-roles.md) decision 4, which keeps a role away from
`resolve`, would change.

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
- 2026-09-28: Checked again; not fired. [R-272](272-more-subagent-roles.md) gave the brain roles
  ([ADR-0072](../../adr/ADR-0072-subagent-roles.md)), so the trigger no longer waits on it. A role
  is a description and one sentence about the form of the reply; it holds no model, no tools and no
  schema, and the runner resolves it after `SubagentRoster.resolve` without passing it there. A
  role that needed a cheap model would first need a model preference, which that record declined.
- 2026-10-03: Checked again; not fired. `SubagentRoster.resolve` is now at `roster.py:43` and
  still returns the `default` for any tainted or tools-enabled spawn before it reads the request;
  the runner calls it at `runner.py:76` and resolves the role after it at `runner.py:81`. The roles
  readings record has no tainted or tools-enabled row. The body called the roster a port, which it
  is not: `SubagentRoster` is a frozen dataclass in the core, and `ports.py` has no roster. The
  trigger now names the record and the search that decide it.
