# The drain bound against a fired task's lease

**Status:** declined 2026-08-09
**Area:** resource-governance
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)

The entry read: "`CORTEX_SWAP_DRAIN_TIMEOUT_S` (default 60 s) bounds quiescing the pool before
anything is evicted. A ticker-fired task holds its admission for up to the schedule lease
(`CORTEX_SCHEDULE_LEASE_S`, default 300 s), so a handoff requested while one is running drains
to a timeout and correctly aborts before evicting anything. That is the designed direction, but
with the shipped defaults it makes an escalation during a scheduled task systematically
impossible rather than occasionally unlucky. The knobs already exist (raise the drain bound
above the lease, or lower the lease), so the fix is a defaults decision informed by real usage."
**The comparison reads a ceiling as a duration.** `drain` waits on one condition,
`while self._in_flight > 0` under `asyncio.timeout(timeout_s)`, and `_in_flight` is moved only by
`admit`, which `SubagentRunner.run` holds around the whole subagent run. So a drain waits out the
remaining runtime of admitted runs and never a lease. The two do meet on one path, a ticker fired
task reaching that same admission through `spawn_subagents`, which is why the entry reads as
plausible; what it gets wrong is which quantity the lease names. The lease is the store's claim
fence and, in `ScheduleTicker.run_once`, the `asyncio.wait_for` cap that cancels a wedged fire: a
**ceiling** on the hold, not its duration. Comparing 60 s to 300 s compares a wait bound to a
cancellation cap, and neither decides the outcome.
**What decides it is a measurement, and the honest word is "usually".** A whole CPU subtask is
200 to 300 s, so a drain meeting one in flight clears it only when 60 s or less remains: roughly
a quarter of arrivals for a single run, fewer for an admitted pair whose releases stagger. That is likely rather than
systematic, which is the word the entry used. The framing was narrow too: an interactive spawn
holds the same admission with no lease at all, and since nothing caps a generation's length (the total
generation cap below) and the 600 s ceiling bounds only the gap between chunks, its hold has no upper bound
at all, so the collision is drain against delegated work of any origin.
**Both proposed knob moves are refused.** Lowering the lease under the drain bound makes drains
succeed by cancelling every fire before its own subtask can finish, breaking the feature to
protect the handoff. Raising the drain bound over the lease covers fires and not interactive
spawns, and no finite value makes the drain reliable while a generation's length is uncapped; the
smallest that even covers a wedge sits above the 600 s ceiling, which is exactly the "do not hold
the handoff open for minutes" the default was chosen for. What is left
is a trade between handoff latency and handoff success, made with a knob that already exists by a
deployment that has met the collision. Killing a subagent mid-stream stays refused (v1 never
does). What landed with the decline is the falsified rationale: the comment on
`DEFAULT_SWAP_DRAIN_TIMEOUT_S` and its restatement in
[modules/brain-core.md](../../modules/brain-core.md) both called 60 s "generous enough for a normal
delegated run to finish", which this repo's own 200 to 300 s measurement denies, and the
[model-swap runbook](../../runbooks/model-swap.md) gained the sizing paragraph that names what the
knob is really up against. **Reopens** on a deployment that reports the collision with the
measured run durations to size against, which is the usage the entry asked for and the only thing
that turns this trade into arithmetic.

## Trail

- 2026-07-17: Opened by the brain-handoff conductor sub-slice, one of three deferrals three areas
  gained that day. The shipped defaults were read as making a handoff requested during a scheduled
  task abort every time, correctly and before evicting anything, which was filed as a defaults
  decision to make against real usage rather than a design change.
- 2026-08-09: Closed as declined, wrong premise and no free move, recorded at the
  [ADR-0030 drain-bound addendum](../../adr/ADR-0030-brain-handoff.md). Traced to the code ahead of the
  usage it asked for, `drain` waits on an in-flight admission and never on a lease, so its stated
  mechanism was a comparison between a wait bound and a cancellation ceiling and the abort it called
  systematic is merely likely. It is the first departure in this area with no arrival beside it.
- 2026-08-09: What landed with the decline is the falsified rationale, the comment on
  `DEFAULT_SWAP_DRAIN_TIMEOUT_S` and its restatement in the core module doc having called 60 s
  generous enough for a normal delegated run to finish, plus the sizing paragraph the model-swap
  runbook gained. It reopens on a deployment that reports the collision with measured run durations.
