# Measure the retry after a weekly rule is refused beside one weekday

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-08

`schedule_weekly.py` refuses, once per turn, a `schedule_task` call with `on_days` when the
person's message names one weekday and no repeat word, and `WEEKLY_DAY_MSG` asks for a one-time
`at`. On 2026-11-08 the refusal fired in one draw only, under a condition where the result also
invited a weekly retry and recall returned earlier draws; that retry kept the weekly rule. Under
the clean condition the cortex chose `at` on its own in 12 of 12 one-time weekday draws, so what
it calls after the refusal is unmeasured
([readings](../../readings/schedule-one-time-weekday.md)).

## What to do

1. Write the row and rule first: the barber message with its first call fixed to the weekly call
   and its result the refusal text, sent to the model host through the recording proxy from a
   second brain, four or more draws; it passes when every next call is a one-time `at` on
   2026-11-10 at 08:00 (or the next Tuesday of the run's date) and none drops the reminder.
2. If a retry keeps the weekly rule or drops the reminder, try a brain-appended note over the
   stored weekly item instead, as the daily note does.

## History

- 2026-11-08: filed by the slot that refused a weekly rule beside one named weekday.
