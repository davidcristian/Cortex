# The drain bound against a fired task's lease

**Status:** declined 2026-08-09
**Area:** resource-governance
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)

The entry compared `CORTEX_SWAP_DRAIN_TIMEOUT_S` (60 s) against `CORTEX_SCHEDULE_LEASE_S` (300 s)
and concluded that a handoff requested during a scheduled task aborts every time.

That comparison reads a ceiling as a duration. `drain` waits on one condition,
`while self._in_flight > 0` under `asyncio.timeout(timeout_s)`, and `_in_flight` is moved only by
`admit`, which `SubagentRunner.run` holds around the whole subagent run. So a drain waits out the
remaining runtime of admitted runs and never a lease. The lease is the store's claim boundary and,
in `ScheduleTicker.run_once`, the `asyncio.wait_for` limit that cancels a wedged fire: a ceiling on
the hold, not its duration.

What decides it is a measurement. A whole CPU subtask is 200 to 300 s, so a drain that meets one in
flight clears it only when 60 s or less remains, which is roughly a quarter of arrivals for a single
run and fewer for an admitted pair whose releases are staggered. That is likely rather than
systematic. The framing was narrow too: an interactive spawn holds the same admission with no lease
at all, and nothing caps a generation's length, so the collision is the drain against delegated work
of any origin.

Both proposed setting changes are refused. Lowering the lease under the drain bound makes drains
succeed by cancelling every fire before its subtask can finish, breaking the feature to protect the
handoff. Raising the drain bound over the lease covers fires and not interactive spawns, and no
finite value makes the drain reliable while a generation's length is uncapped; the smallest that
even covers a wedge sits above the 600 s ceiling, which is exactly what the default was chosen to
avoid. What is left is a trade between handoff latency and handoff success, made with a setting that
already exists, by a deployment that has met the collision. Killing a subagent mid-stream stays
refused.

The false rationale was fixed with the decline: the comment on `DEFAULT_SWAP_DRAIN_TIMEOUT_S` and
its restatement in [modules/brain-core.md](../../modules/brain-core.md) both called 60 s generous
enough for a normal delegated run to finish, which this repo's own 200 to 300 s measurement denies,
and the [model-swap runbook](../../runbooks/model-swap.md) gained a sizing paragraph.

It reopens on a deployment that reports the collision with measured run durations to size against.

## History

- 2026-07-17: Opened by the brain-handoff conductor sub-slice, filed as a defaults decision to make
  against real usage rather than a design change.
- 2026-08-09: Declined, on a wrong premise and no free move, recorded at
  [ADR-0030](../../adr/ADR-0030-brain-handoff.md) decision 4. Traced to the code ahead of the usage
  it asked for.
- 2026-08-09: The false rationale in the comment, the core module doc and the model-swap runbook was
  fixed with the decline.
