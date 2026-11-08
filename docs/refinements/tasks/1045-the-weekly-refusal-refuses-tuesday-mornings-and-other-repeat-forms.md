# The weekly refusal refuses Tuesday mornings and other repeat forms

**Status:** open, actionable
**Area:** schedules
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-08

`names_one_weekday` in `schedule_weekly.py` reads a message as naming one weekday and no repeat,
so `weekly_unasked` refuses a `schedule_task` call with `on_days`, for these requests for a weekly
rule (unit level, `True` for each):

- a weekday with a plural part of the day: "Remind me Tuesday mornings to take the bins out",
  "on Tuesday evenings at 7", "Tuesday nights";
- English repeat words `_MAY_REPEAT` does not hold: "going forward", "ongoing", "indefinitely",
  "permanently", "forever", "all the time", "keep it going";
- "Rappelle-moi un mardi sur deux" (every other Tuesday), "Recuérdame martes por medio",
  "Erinnere mich Dienstag für Dienstag", and "le mardi 9h", which the `(?!\s*\d)` after `le mardi`
  reads as a date.

Live, on the stack brain built from `d82ce5a12`
([readings](../../readings/schedule-one-time-weekday.md#audit-draws-on-the-refusal-2026-11-08)),
`Remind me Tuesday mornings at 8 to take the bins out.` had its first call, weekly on Tuesday at 08:00, refused; the model
called the same rule again and the once-per-turn retry stored it. One draw kept the rule because
the model repeated the call, which the refusal text asks it not to do.

## What to do

1. Write near misses first: "Remind me Tuesday morning" (singular) and "Remind me on Tuesday, the
   morning shift" must stay refused.
2. Read a plural part of the day after the weekday (`mornings`, `afternoons`, `evenings`,
   `nights`), the English words above and `sur deux` as words that may ask for a repeat. A tool
   refusal keeps the tool when unsure.
3. Replay every recorded draw message through the old and new reader before committing.

## History

- 2026-11-08: filed by the night's audit slot, from a unit probe and one live draw.
