# The cortex uptake of the role property is unmeasured

**Status:** open, actionable
**Area:** subagents
**Origin:** [ADR-0072](../../adr/ADR-0072-subagent-roles.md)

The spawn spec now offers a `role` enum on each object item, with a note and an inline example
(`build_spawn_spec` in `brain/packages/core/src/cortex_core/spawn_spec.py`). Whether the deployed
cortex names a role, and names the right one for the subtask it writes, has not been read. The
model choice was measured the same way before: 16 turns inviting delegation produced 16 delegations,
one batch of 15 recorded with a `model` key ([ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md)
decision 8).

The probe to extend is `brain/packages/orchestrator/tests/test_spawn_nudge_live.py`. It builds its
own `SubagentRunner` without `roles`, so it sends the spec with no `role` property until it passes
`SHIPPED_ROLES`. A row reads, over prompts that each ask for one summary, one extraction or one
lookup, how many spawn items name a role and how many name the matching one. A null result is no
item naming a role, which would say the property costs schema tokens for nothing on this cortex; a
wrong match rate above the right one would say the names or descriptions mislead it, which is
evidence for the maintainer's pick of names. Done when the rows are in a readings record and
ADR-0072 states them.

## History

- 2026-09-28: Filed when [R-272](272-more-subagent-roles.md) added the property without a reading
  of the cortex using it.
