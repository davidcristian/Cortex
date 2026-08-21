# The run deadline's place under the queue for it is written only in prose

**Status:** open, actionable
**Area:** subagents
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

Four bounds govern a delegated run and three of the relations between them are now refused at boot:
`CORTEX_SUBAGENTS_RUN_TIMEOUT_S` above `CORTEX_SUBAGENTS_STALL_TIMEOUT_S`, and
`CORTEX_TOOLS_CALL_TIMEOUT_S` below the run deadline, each with a validator or a composition-root
check behind it. The fourth is stated and enforced nowhere.

`docs/runbooks/subagents-cpu.md` says the deadline "lands between the two bounds either side of it,
above the stall ceiling and below the admission wait, so a run can never hold its admission longer
than a peer will queue for it". The first half is enforced by
`SubagentsConfig._the_run_deadline_must_outlast_the_stall_ceiling`. The second half is not enforced
by anything: `run_timeout_s` and `admission_wait_s` are both fields of `SubagentsConfig` and no
validator compares them, so a deployment that raises the run deadline past
`CORTEX_SUBAGENTS_ADMISSION_WAIT_S`, or lowers the wait under the deadline, ships and reads as a
pool that refuses spawns under load. A queued peer gives up while the run holding its room is still
inside the deadline this deployment granted it, which is a refusal the operator cannot connect to
either knob.

This is the cheapest of the four to close, both numbers being fields of one class, so it is a
validator beside the stall-ceiling one rather than anything at the composition root. Two things to
decide when writing it. The wait may be **zero**, which means never queue at all
(`Field(..., ge=0)` and the runbook's own "zero means never queue"), and a deployment that never
queues has no relation to keep, so zero has to pass rather than fail as the smallest possible
inversion. And the comparison wants the same strictness argument the neighbours got: equality here
means a peer gives up at the exact instant the run it waited for releases, which is the race the
other two refuse.

## Trail

- 2026-08-21: Filed by the close of
  [363](363-the-call-bound-and-the-run-bound-are-unordered.md), which ordered the innermost of the
  four bounds and made the unordered fourth relation visible by contrast. Recorded in the ADR-0009
  ordering addendum.
