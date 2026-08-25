# Nothing counts how often the CPU re-run fires, so the doubled hold is sized from reasoning

**Status:** open, fix when it bites
**Area:** subagents
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Trigger:** The first deployment observed refused at the admission bound, or any retune of the run
deadline or the admission wait.

Opened 2026-08-25 by the close of
[R-392](392-a-re-runs-second-deadline-outlasts-the-queue.md), which made the admission wait outlast
the whole hold a task can take rather than one attempt's deadline.

`SubagentRunner._placed` logs a warning when a GPU-placed attempt is re-run on the CPU, and that is
the only trace the path leaves. Nothing counts the warnings, nothing carries the re-run into the
result the cortex reads except as a sentence inside `detail`, and no metric anywhere says what
fraction of spawns take two attempts. So the bound that now sits above two whole deadlines is sized
against a path whose real frequency nobody knows: the close that raised it argued the window from
reading `_placed`, `PlacedAttempt.run` and the adapter's error translation, not from a deployment.

That mattered once already. The entry this closes narrowed its own window on 2026-08-23 by
reasoning about which arm a stalled stream lands in, got the arm wrong, and therefore got the window
wrong in the safe-sounding direction. Reasoning about this path has a track record of being off by
the size of the thing it is estimating.

**Why it was left.** Counting is not free of design. The runner writes structured log records with
the dispatch stamp's vocabulary (ADR-0009 one-vocabulary addendum), and a count wants somewhere to
live that survives a restart, which is a store rather than a logger, which is a port question. A
bare counter in the runner would be process-local state on an object whose whole contract is that
it holds none between calls, so the honest shapes are a field on the persisted `SubagentResult`, a
Redis counter beside the `TaskStore`, or a log record shaped for grepping and nothing more.

**What would close it.** Decide which of those three, and on what the number is then used for. The
narrow version is the third: give the existing warning a record field naming the placement it fell
back from, so `grep` over a week of a real deployment answers the question the next retune needs.
The wider one is a persisted counter, which is the only version that survives the brain restarting
and the only one a health surface could ever read. Either way the thing to write down is the
fraction, because what the bound is sized against is not whether the path fires but how often a
peer is queued behind one that did.

## Trail

- 2026-08-25: opened by the close of
  [R-392](392-a-re-runs-second-deadline-outlasts-the-queue.md), whose decision raised the admission
  wait above `ATTEMPTS_PER_ADMISSION` whole run deadlines and could size that window only from
  reading the code.
