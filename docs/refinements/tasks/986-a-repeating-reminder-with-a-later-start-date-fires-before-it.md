# A repeating reminder with a later start date fires before it

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-05

`schedule_task` has no argument for the first day of a repeat: `at_time` with `on_month_days`,
`on_days` or `on_dates` fires from the next matching day, and `at` beside `at_time` is refused as
invalid. On the overlay, "Remind me to pay the gas bill on the 15th, starting 15 June." on
2026-11-05 stored `on_month_days` [15] with `due_at` 2026-11-15T09:00, seven months before the
named start, and the reply said "every month on the 15th at 09:00, starting this month." with no
note that the named start was not kept
([readings](../../readings/overlay-end-to-end-smoke.md#the-flow-on-the-nights-closing-tree-2026-11-05)).

## What to do

1. Add a start date to a rule repeat behind the schedule port: an optional ISO date argument whose
   first occurrence is the first rule match on or after it, stored on the record and covered by
   the schedule contract tests.
2. Until then, or as well, a typed check of the reply that names a start the record does not hold
   and a brain-appended note, as `schedule_claim.py` does for a claimed reminder.
3. Write rows into the readings before drawing: the gas bill message, "Starting May 1, remind me
   on the 1st to pay rent." and "From 3 March, remind me every 4 weeks to change the water
   filter.", scored by whether the stored first `due_at` is on or after the named start.

## History

- 2026-11-05: filed from the end to end smoke flow on the Linux shell.
