# A reminder with a day and no time can fire at midnight

**Status:** done 2026-11-06
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

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

1. Apply the recorded patch of the 00:00 refusal and its 38 tests, listed as cases in the
   [day-only readings](../../readings/schedule-day-only-times.md): a typed check of
   a `schedule_task` or `edit_scheduled` call whose time of day is 00:00 (`at` or `at_time`) when
   the turn's message names no midnight form; the result names the default, 09:00 in the schedule
   zone, and asks the model to call again. It refuses once per turn and a second call with 00:00
   runs, so it fails toward storing the reminder.
2. For the unnamed time, try the brain-appended form first. `ToolRun` holds only a name and an
   ok value, so the closing notes (`limit_notes` in `closing_notes.py`) cannot read the stored
   time from the runs; `run_round` in `dispatch_round.py` sets `TaintLedger.monthly_stored` from a
   call and its result, and the stored time of day is passed the same way: a ledger field set
   from a successful `schedule_task` or `edit_scheduled` result (its text starts
   `scheduled reminder <id>: due <date> <HH:MM>`; the call's `at_time` or `at` holds it too), read
   by `limit_notes`, which appends a note naming that time when the reply names no time of day (a
   clock figure, am or pm, noon or midnight), as `schedule_claim.py` appends its note.
3. Draw the candidate with both on rows D1 to D7 and ship only if the pre-written pass rule
   passes; the refusal alone does not change whether a reply names the time.

## History

- 2026-11-05: filed from the start date rows.
- 2026-11-06: premise checked in `schedule_args.py`, `schedule_verb_args.py` and the
  `schedule_task` spec: no typed default or check exists. Six day-only rows and the pass rule
  were written and a baseline of 18 draws taken: 1 at 00:00, 8 replies naming the time. The edit
  verb was changed to keep the item's own time when a call moves a day without `at_time`, so a D6
  edit takes one call. The 00:00 refusal was built with 38 tests and drawn twice on D1 to D6: 12
  stored draws, none at 00:00, the reply naming the time in 5 of 12 (never D1, D4 or D6), so the
  pass rule failed on the unnamed time alone and the refusal did not ship; its patch is recorded
  in the readings, row D7 (a named midnight) was added, and the appended time is the next step.
- 2026-11-06: closed. The recorded refusal was applied with its 38 tests, and the stored time is
  appended: `run_round` sets `TaintLedger.stored_time` from a successful timed `schedule_task` or
  `edit_scheduled` result, the field crosses the handoff record and its codec, and `limit_notes`
  appends `STORED_TIME_NOTE` when the reply names no time of day. Drawn twice on D1 to D7: 14
  stored draws, none at 00:00 for D1 to D6, both D7 draws at the named midnight, every reply
  naming the time (6 by the note), so the pass rule passed and both shipped.
