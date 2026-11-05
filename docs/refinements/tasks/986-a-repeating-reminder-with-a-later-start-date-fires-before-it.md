# A repeating reminder with a later start date fires before it

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-05

On the overlay, "Remind me to pay the gas bill on the 15th, starting 15 June." on 2026-11-05
stored `on_month_days` [15] with `due_at` 2026-11-15T09:00, seven months before the named start,
and the reply said "every month on the 15th at 09:00, starting this month." with no note that the
named start was not kept
([readings](../../readings/overlay-end-to-end-smoke.md#the-flow-on-the-nights-closing-tree-2026-11-05)).
`schedule_task` then had no argument for the first day of a repeat. It now takes `starting`, an
ISO date: the first fire is the rule's first match on or after it, read in the rule's zone, and a
day before today is refused with today's date
([ADR-0065](../../adr/ADR-0065-wall-clock-schedule-times.md) decision 2). Whether the cortex
passes it is not yet measured.

## What to do

1. Write rows into the readings before drawing: the gas bill message, "Starting May 1, remind me
   on the 1st to pay rent." and "From 3 March, remind me every 4 weeks to change the water
   filter.", scored by whether the stored first `due_at` is on or after the named start.
2. If the rows show stored firsts before the named start, add a typed check of the reply that
   names a start the record does not hold, with a brain-appended note, as `schedule_claim.py`
   does for a claimed reminder.

## History

- 2026-11-05: filed from the end to end smoke flow on the Linux shell.
- 2026-11-05: `schedule_task` takes `starting`; an edit that sets a rule still computes from now
  and is filed as [R-987](987-an-edited-repeat-with-a-later-first-day-fires-before-it.md).
