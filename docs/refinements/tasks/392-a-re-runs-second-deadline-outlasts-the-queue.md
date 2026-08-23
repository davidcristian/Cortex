# A re-run's second deadline outlasts the queue the first was ordered against

**Status:** open, actionable
**Area:** subagents
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

`SubagentsConfig` now refuses a run deadline at or above `CORTEX_SUBAGENTS_ADMISSION_WAIT_S`, so a
run can never hold its admission for as long as a peer will queue for that admission. What it
compares is **one attempt's** deadline, and a task can hold one admission through two of them.

`SubagentRunner._placed` re-runs a GPU-placed `AttemptFailure.INFERENCE` once on the CPU inside the
same `scheduler.admit` context, and `PlacedAttempt` arms `asyncio.timeout(self._bounds.timeout_s)`
per attempt rather than per task, deliberately: a re-run handed what a failed attempt left of a
deadline would be refused before it began. The runner's own docstring states the consequence, that
a task can hold its admission for two deadlines rather than one. So the worst-case hold is twice
`CORTEX_SUBAGENTS_RUN_TIMEOUT_S`, and the shipped pair does not clear it: twice the shipped
deadline is above the shipped wait, which is why the validator compares the bare number.

Closing this is a measurement rather than a comparison, and that is the whole of why it is a task
of its own. Both numbers are measured on the shipped CPU entry, the deadline at four times the
longest whole subtask and the wait at twice the serial batch wait these budgets produce, so any
pair that clears the doubled relation is a re-derivation of one of them. The candidates, none of
them free: raise the wait above twice the deadline, which lengthens how long a refused spawn takes
to come back and wants the batch measured rather than single subtasks, which is the measurement
[207](207-whole-subtask-figure-off.md) is already waiting on and names a retune of either bound as
its own trigger, so the two want doing together; lower
the deadline, which cuts a legitimate long subtask on the slowest tier this repo ships; or bound
the whole task rather than each attempt, which trades the re-run's own reason for existing, a
second attempt being worth nothing if it starts against a spent clock.

The narrow reading is that the re-run path is rare (only a GPU placement, only an inference
failure, never a truncation) and the honest one is that the relation as written is false along it.
Whichever number moves, the runbook sentence and the validator's own "what it does not promise"
both want rewriting with it.

## Trail

- 2026-08-23: Opened by the close of
  [369](369-the-run-deadline-under-the-queue-is-prose-only.md), which ordered the run deadline
  against the queue for it and found, while writing the check, that the relation it was enforcing
  is false along the CPU re-run path and cannot be made true by any comparison over the shipped
  numbers. Recorded in the ADR-0009 queue addendum.
- 2026-08-23: Re-derived against the tree and left open, its trigger not having fired. The
  mechanism above is exactly what the code does: `subagent_attempt.py` arms
  `asyncio.timeout(self._bounds.timeout_s)` inside the attempt, and `SubagentRunner._placed` calls
  that attempt twice inside one `scheduler.admit`, so two whole deadlines fit in one admission.
  Neither of the two bounds has been retuned since the commit that declared it, and no spawn has
  been observed refused at the admission bound, so the batch measurement
  [207](207-whole-subtask-figure-off.md) is waiting on remains what this waits on too.
  What the re-derivation does sharpen is the size of the violating window, which the text above
  overstates as the whole re-run path. A stalled stream is an `INFERENCE` failure rather than a
  truncation: the attempt's `TimeoutError` arm reports the inner-timeout message under
  `AttemptFailure.INFERENCE` whenever the timer that fired was not the attempt's own. So the
  ordinary wedge does re-place, and it re-places at the moment the stall ceiling fired rather than
  at the deadline, which puts the common doubled hold at 600 s plus a fresh 2400 s, comfortably
  inside the 3600 s wait. The shipped pair fails the doubled relation only when a first attempt
  ends in `INFERENCE` after spending more than 1200 s of its deadline, which is a backend dying
  late in a stream that never went quiet long enough to trip the ceiling. That is narrower than
  twice the deadline and is not a reason to close this, but it is the window a retune should be
  sized against rather than the factor of two.
