# A reminder on a named weekday can be stored to repeat every week

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-08

On the stack brain at 02:39 on 2026-11-08, `Remember that I have the barber on Tuesday. Give me a
shout at 8 that morning.` made the cortex call `schedule_task` with `at_time` and `on_days`, a rule
for every Tuesday at 8 (`rule: {"hour": 8, "minute": 0, "days": [1]}`). The message names one
Tuesday and no repeat. The reply said "every Tuesday at 8:00 AM", so the person is told, but the
reminder fires each week until cancelled. `schedule_daily.py` appends a note only to a rule that
repeats every day, and `schedule_yearly.py` refuses only a monthly rule beside a yearly date; no
reader covers a weekly rule the message did not ask for
([readings](../../readings/side-effect-tools-second-clause.md)).

## What to do

1. Write rows and a pass rule first: the barber message and two or three more one-time weekday
   requests, beside weekly ones (`every Tuesday`, `on Tuesdays`) that must keep their rule.
2. Try the brain-appended form first: a note after a typed check of the call and the message, as
   `schedule_daily.py` does for a daily rule, rather than a model-read result.

## History

- 2026-11-08: filed by the slot that kept the reminder and sound tools beside an English second
  clause, from one draw on the stack; not replicated.
