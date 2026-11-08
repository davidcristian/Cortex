# Name the next date in the refusal of a weekly rule beside one weekday

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-08

`WEEKLY_DAY_MSG` (`schedule_weekly.py`) asks the cortex to call again with `at` set to "the
ISO-8601 date-time of its next date", so the cortex computes that date itself. In a replay of two
recorded requests whose weekly first call was refused, 3 of 8 retries were a one-time `at` one day
off the named weekday, and the one live retry of that shape on the start build was a day late too
([readings](../../readings/schedule-one-time-weekday.md), rows B1 and B2). The weekday check in
`schedule_weekday.py` now refuses such a retry once and names the dates on either side; after it
the next call was on the right date in 8 of 8 replays. The reminder therefore ends on the right
day, at the cost of one more round.

## What to do

1. Write the rows and the rule first: B1 and B2 with a refusal text that names the next date of
   the named weekday, four or more draws each; it passes when every next call is a one-time `at`
   on the date in the table.
2. The weekly refusal has no `at` to count from, so naming the date needs today's date in the
   person's zone in the dispatch round, which `ToolLoopContext` does not hold today. Read how
   `schedule_args.py` gets its `DisplayZone` before adding a field.

## History

- 2026-11-08: filed by the slot that refused a one-time date one day off the named weekday.
