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

Replayed, a refusal of a weekly rule asked in such words drops the repeat: 5 of 8 next calls were
a one-time `at` on the named date, with nothing shown
([readings](../../readings/schedule-weekly-false-refusal.md)). A longer word list fixes only the
forms it names, and a refusal only beside a one-time marker would lose the catch of a correct
refusal recorded tonight.

## What to do

1. Keep the refusal, which fixes a real weekly call for a one-time request, and add a note the
   brain appends when a turn whose weekly call was refused then stores a one-time item: "(The
   reminder set in this turn is for one day only. Ask to make it weekly if you meant every
   week.)". A reply note shows when unsure, so it is not held back by any reading of the reply.
2. Set the flag in `run_round` (`dispatch_round.py`) on a successful `schedule_task` call with
   `at` after `LoopRecord.weekly_refused` holds a call, in the deep phase too, pass it across the
   handoff record as `daily_stored` is (`handoff.py`, `handoff_codec.py`), and append the note in
   `limit_notes` (`closing_notes.py`) beside the daily note.
3. Write rows and a pass rule first: F1 and F2 drawn live, the note shown in every draw that
   stores a one-time item after the refusal, and absent from W1 to W4 draws with no refusal.

## History

- 2026-11-08: filed by the night's audit slot, from a unit probe and one live draw; the same
  slot made `_MAY_REPEAT` read the plural parts of the day, five English words and `sur deux`.
- 2026-11-08: the next slot replayed two of the forms after the refusal and found the repeat
  dropped in 5 of 8, so the remedy is a note beside the refusal rather than more repeat words.
