# The run deadline's place under the queue for it is written only in prose

**Status:** done 2026-08-23
**Area:** subagents
**Origin:** [ADR-0047](../../adr/ADR-0047-delegated-run-bound-ordering.md)

Four bounds govern a delegated run. Two of the relations between them are refused at boot:
`CORTEX_SUBAGENTS_RUN_TIMEOUT_S` above `CORTEX_SUBAGENTS_STALL_TIMEOUT_S`, and
`CORTEX_TOOLS_CALL_TIMEOUT_S` below the run deadline. A third was stated and enforced nowhere.

`docs/runbooks/subagents-cpu.md` says the deadline sits between the two bounds either side of it,
above the stall ceiling and below the admission wait, so a run can never hold its admission longer
than a peer will queue for it. The first half is enforced by
`SubagentsConfig._the_run_deadline_must_outlast_the_stall_ceiling`. The second half was enforced by
nothing: `run_timeout_s` and `admission_wait_s` are both fields of `SubagentsConfig` and no
validator compared them, so a deployment that raised the run deadline past
`CORTEX_SUBAGENTS_ADMISSION_WAIT_S`, or lowered the wait under the deadline, would ship and read as
a pool that refuses spawns under load.

This is the cheapest of the four to close, both numbers being fields of one class, so it is a
validator beside the stall-ceiling one. Two things to decide when writing it. The wait may be zero,
which means never queue at all, and a deployment that never queues has no relation to keep, so zero
has to pass. And the comparison needs the same strictness argument the neighbours got: equality
here means a peer gives up at the exact instant the run it waited for releases.

## History

- 2026-08-21: Filed by the close of
  [363](363-the-call-bound-and-the-run-bound-are-unordered.md), which ordered the innermost of the
  four bounds and made the unordered relation visible by contrast. Recorded in ADR-0047 decision 3.
- 2026-08-23: Done as `SubagentsConfig._the_run_deadline_must_fit_inside_the_queue_for_it`, a
  validator beside the stall-ceiling one, comparing two fields of the one class. Both decisions
  went the way this entry proposed and for the reasons it gave: strictly under, since equality is a
  peer giving up at the instant the room comes back, and a zero wait passes, that being the setting
  where nothing queues. The entry's own count was out by one, "three of the relations refused at
  boot" naming two, which is the true number. What it could not know is that the runbook sentence
  it quotes is false of the shipped numbers along one path: `_placed` re-runs a GPU-placed
  inference failure inside the same admission under a deadline started fresh, so a task can hold
  its room for two deadlines, and twice the shipped deadline is above the shipped wait. Comparing
  the real hold would refuse the stack this repo ships, so the validator compares one attempt's
  deadline, the runbook now says which half is enforced, and the other half is filed as
  [392](392-a-re-runs-second-deadline-outlasts-the-queue.md). A second entry,
  [393](393-the-admission-waits-default-is-tied-to-nothing.md), was opened by reading the constant
  registry while writing this: the wait's shipped default appears in two documents and is compared
  by no entry. Recorded in ADR-0047 decision 4.
