# The reply check misses a task claimed beside a reminder

**Status:** open, waiting for its trigger
**Area:** scheduling
**Origin:** [ADR-0074](../../adr/ADR-0074-replayed-tool-runs.md)
**Verified:** 2026-10-15
**Trigger:** a third turn of the R-834 rows whose reminder call succeeded and whose reply says the task was scheduled

The reply check ([ADR-0074](../../adr/ADR-0074-replayed-tool-runs.md) decision 7) reads a turn's
runs as names and outcomes only, so one `schedule_task` run that succeeded clears every claim in
the reply, whatever kind that run stored. A turn whose task call is refused with
`TAINTED_TASK_MSG` and whose reminder call then succeeds can reply that the task was scheduled,
and no note is added. None of the 50 third turns of 2026-10-13 made a scheduling call that
succeeded, so the shape was not seen
([readings](../../readings/task-claimed-without-call.md#a-reply-check-against-the-turns-runs));
under the earlier refusal text, 1 of 3 such turns made the reminder call
([overlay-file-and-memory-flows.md](../../readings/overlay-file-and-memory-flows.md#a-reminder-and-a-task-after-it)).

## What to do

1. When the trigger fires, decide whether a scheduling run records the kind it stored (`ToolRun`
   keeps only the name and the outcome, ADR-0074 decision 2) or whether the check compares the
   kind a reply names with the kinds stored. Write rows and a pass rule first.

## History

- 2026-10-13: filed while closing
  [R-834](834-a-reply-claims-a-task-it-never-tried-to-schedule.md), whose rows had no third turn
  with a scheduling call that succeeded.
- 2026-10-15: Not fired. The rows added to the readings on 2026-10-13 are a deep reply after a
  reminder the cortex set, with no task call, so none is a refused task beside a reminder.
