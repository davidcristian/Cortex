# A re-run's second deadline outlasts the queue the first was ordered against

**Status:** done 2026-08-25
**Area:** subagents
**Origin:** [ADR-0047](../../adr/ADR-0047-delegated-run-bound-ordering.md)

`SubagentsConfig` refuses a run deadline at or above `CORTEX_SUBAGENTS_ADMISSION_WAIT_S`, so a run
can never hold its admission for as long as a peer will queue for it. What it compares is one
attempt's deadline, and a task can hold one admission through two attempts.

`SubagentRunner._placed` re-runs a GPU-placed `AttemptFailure.INFERENCE` once on the CPU inside
the same `scheduler.admit` context, and `PlacedAttempt` starts `asyncio.timeout(self._bounds.timeout_s)`
per attempt rather than per task, deliberately: a re-run handed what a failed attempt left of a
deadline would be refused before it began. So the worst case hold is twice
`CORTEX_SUBAGENTS_RUN_TIMEOUT_S`, and twice the shipped deadline is above the shipped wait.

Closing this needs a measurement rather than a comparison. Both numbers were measured on the
shipped CPU tier, the deadline at four times the longest whole subtask and the wait at twice the
serial batch wait these budgets produce, so any pair that satisfies the doubled relation means
recomputing one of them. The candidates: raise the wait above twice the deadline, which lengthens
how long a refused spawn takes to come back and needs the batch measured, which is what
[207](207-whole-subtask-figure-off.md) waits on; lower the deadline, which cuts a legitimate long
subtask on the slowest tier this repo ships; or bound the whole task rather than each attempt,
which removes the re-run's reason for existing.

## History

- 2026-08-23: opened by the close of
  [369](369-the-run-deadline-under-the-queue-is-prose-only.md), which ordered the run deadline
  against the queue for it and found, while writing the check, that the relation it enforces is
  false along the CPU re-run path and cannot be made true by any comparison over the shipped
  numbers. Recorded in ADR-0047 decision 4.
- 2026-08-23: checked against the tree and left open, its trigger not having fired.
  `subagent_attempt.py` starts `asyncio.timeout(self._bounds.timeout_s)` inside the attempt, and
  `SubagentRunner._placed` calls that attempt twice inside one `scheduler.admit`, so two whole
  deadlines fit in one admission. Neither bound has been retuned since the commit that declared
  it, and no spawn has been seen refused at the admission bound. This reading narrowed the
  violating window: a stalled stream is an `INFERENCE` failure rather than a truncation, so the
  ordinary stall re-places at the moment the stall ceiling fired rather than at the deadline,
  putting the common doubled hold at 600 s plus a fresh 2400 s, inside the 3600 s wait. On that
  reading the shipped pair fails the doubled relation only when a first attempt ends in
  `INFERENCE` after spending more than 1200 s of its deadline.
- 2026-08-25: closed by raising the wait and comparing the hold. The narrowing above is wrong in
  one sentence the rest depends on: a stalled stream does not reach `INFERENCE` through the
  attempt's `TimeoutError` branch, because `httpx.ReadTimeout` is not a subclass of the builtin
  `TimeoutError` and `LlamaCppBackend` turns it into an `InferenceError` first. The conclusion
  survives, but the window does not: a read timeout bounds one socket read, so a stall fires at
  the last chunk plus the ceiling rather than at the ceiling, and the violating window is every
  stall after the first ten minutes of a stream plus every mid-stream transport failure at any
  elapsed time. Of the three candidates the measurement chose the first. A live full batch put the
  deadline's derivation on two independent routes to 2400 s, so lowering it would cut work on the
  slow end of a factor-of-two interval; the wait had about 350 s of slack over twice its measured
  batch wait, so the wait is the number with room to move, and raising it can never refuse a spawn
  the old bound admitted. `DEFAULT_ADMISSION_WAIT_S` is 7200 s, three run deadlines, and
  `SubagentsConfig` now compares `ATTEMPTS_PER_ADMISSION * run_timeout_s` with it, that constant
  being declared beside the bounds and tied to `_placed` by the runner suite's counting backend
  rather than by a sentence. The runbook's "recorded rather than enforced" half is gone. Recorded
  in ADR-0047 decision 4, with the wait's superseded derivation at ADR-0012 and the batch itself
  at ADR-0005. It opened
  [R-429](429-nothing-counts-how-often-the-cpu-re-run-fires.md): the hold is enforced but nobody
  counts how often the re-run that produces it happens.
