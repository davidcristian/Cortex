# The weekly refusal refuses a weekly rule asked in rarer forms

**Status:** open, actionable
**Area:** schedules
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-08

`names_one_weekday` in `schedule_weekly.py` reads a message as naming one weekday and no repeat,
so `weekly_unasked` refuses a `schedule_task` call with `on_days`, for these requests for a weekly
rule (unit level, `True` for each):

- English repeat words `_MAY_REPEAT` does not hold: "all the time", "keep it going";
- "Recuérdame martes por medio", "Erinnere mich Dienstag für Dienstag", and "le mardi 9h", which
  the `(?!\s*\d)` after `le mardi` reads as a date.

The plural parts of the day ("Tuesday mornings", "evenings", "nights", "afternoons"), "going
forward", "ongoing", "indefinitely", "permanently", "forever" and "un mardi sur deux" had the same
effect until `_MAY_REPEAT` read them. Live, on the stack brain built from `d82ce5a12`
([readings](../../readings/schedule-one-time-weekday.md#audit-draws-on-the-refusal-2026-11-08)),
`Remind me Tuesday mornings at 8 to take the bins out.` had its first call, weekly on Tuesday at
08:00, refused; the model called the same rule again and the once-per-turn retry stored it.

## What to do

1. Write near misses first: "Remind me on Tuesday, time to go" and "le mardi 10" must stay
   refused.
2. Read the forms above as words that may ask for a repeat, `für` only between two weekdays. A
   tool refusal keeps the tool when unsure.
3. Replay every recorded draw message through the old and new reader before committing.

## History

- 2026-11-08: filed by the night's audit slot, from a unit probe and one live draw; the same
  slot made `_MAY_REPEAT` read the plural parts of the day, five English words and `sur deux`.
