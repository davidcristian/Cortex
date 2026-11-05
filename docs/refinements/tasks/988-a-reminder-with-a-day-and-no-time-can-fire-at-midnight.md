# A reminder with a day and no time can fire at midnight

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-05

A request that names a day and no time of day can be stored at 00:00. In the start date rows of
2026-11-05, two of eight stored draws did: "Starting May 1, remind me on the 1st to pay rent." as
`at_time` 00:00, and "From 3 March, remind me every 4 weeks to change the water filter." as `at`
2027-03-03T00:00; the other six used 09:00, and neither reply named the time
([readings](../../readings/schedule-start-dates.md)). A reminder at midnight fires while the
person is likely asleep.

## What to do

1. Write rows of day-only requests into the readings and draw a baseline of the stored times.
2. If midnight repeats, choose between a deployment default time stated in the `schedule_task`
   spec and a typed check of the call that names the missing time in its result, and measure it.

## History

- 2026-11-05: filed from the start date rows.
