# A reminder with a day and no time can fire at midnight

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-06

A request that names a day and no time of day can be stored at 00:00. Over two nights, 3 of 26
stored day-only draws were: two of eight start date draws on 2026-11-05
([readings](../../readings/schedule-start-dates.md)) and one of eighteen day-only draws on
2026-11-06, a yearly birthday whose first call already gave `at_time` 00:00
([readings](../../readings/schedule-day-only-times.md)). The other 23 used 09:00, and the reply
named the time in 8 of the 18 draws of 2026-11-06, never for a one-time day, an interval from a
date or an edit. A reminder at midnight fires while the person is likely asleep.

The typed arguments have no missing-time case: a one-time reminder gives `at`, an ISO-8601
date-time, and every wall-clock repeat gives `at_time`. The spec text says "e.g. 09:00" and names
no default, so the model picks the time, and a check of the call alone cannot tell a chosen 00:00
from a requested one.

## What to do

1. Build the remedy against the rows and pass rule of 2026-11-06, tests first. The proposed shape:
   a typed check of a `schedule_task` or `edit_scheduled` call whose time of day is 00:00 (`at`
   or `at_time`) when the turn's message names no midnight form (`midnight`, `0:00`, `00:00`,
   `12 am`, `12:00 am`); the result names the deployment default, 09:00 in the schedule zone, and
   asks the model to call again with the time the person meant or that default. The check refuses
   once per turn and a second call with 00:00 runs, so it fails toward storing the reminder.
   Near-miss tests before the code: `tonight at 0:00`, `at 12 am`, `at midnight`, and a message
   with `12 pm`.
2. For the unnamed time, try the brain-appended form first: when the stored item's time of day is
   absent from the reply, append the time, as `schedule_claim.py` appends its note.
3. Draw the candidate on rows D1 to D6 and ship only if the pre-written pass rule passes.

## History

- 2026-11-05: filed from the start date rows.
- 2026-11-06: premise checked in `schedule_args.py`, `schedule_verb_args.py` and the
  `schedule_task` spec: no typed default or check exists. Six day-only rows and the pass rule
  were written and a baseline of 18 draws taken: 1 at 00:00, 8 replies naming the time. Left
  open for the build; the edit row's double call is task 990.
