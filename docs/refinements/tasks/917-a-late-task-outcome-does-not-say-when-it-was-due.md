# A late task outcome does not say when it was due

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0066](../../adr/ADR-0066-reminder-toast-and-card.md)
**Verified:** 2026-10-28

A scheduled task that falls due while the brain cannot run, as across a sleep of the machine, runs
when the brain runs again. Its toast title is `Cortex task` with no due time, and its card's
`due_label` is empty, while a late reminder names its due time in both (decision 11 of ADR-0066).
`ScheduleTicker._fire_task` sets the fire time after the subagent run ends, so the late margin
measured against it would read a run longer than the margin as a late fire. That is why neither
the toast nor `reminder_to_proto` applies the rule to a task today.

## What to do

1. Measure a task's lateness from its claim, the `now` that `ScheduleTicker.run_once` claims
   with, rather than from the end of its run, and add the due phrase to the task's toast title on
   the same `is_late_fire` rule.
2. For the card, keep what the list needs to apply the same rule, such as the run's start beside
   `deliverable_due_at`, in both schedule stores and the Redis codec, `None` on an older record.
3. Test both paths, and state the rule for tasks in ADR-0066 decision 11.

## History

- 2026-10-28: filed from
  [R-906](906-a-late-reminder-does-not-say-when-it-was-due.md), whose due label covers reminders
  only.
