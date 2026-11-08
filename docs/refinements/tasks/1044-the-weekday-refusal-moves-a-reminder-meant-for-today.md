# The weekday refusal moves a reminder meant for today

**Status:** open, actionable
**Area:** schedules
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-08

`weekday_mismatch` in `schedule_weekday.py` refuses a one-time `at` one day off the one weekday
the message names, unless `_MOVES_DAY` reads a word that moves the day. A message that names the
weekday of the thing the reminder is for, and asks for the reminder today, has no such word:

- a time today with no day word: "Remind me at 6pm to put the bins out for Monday's collection",
  "Remind me this evening to prepare for Monday's meeting", "Remind me in an hour to call about
  Monday" and the same in French, German and Spanish (`ce matin`, `in einer Stunde`, `en una
  hora`) are all refused on a Sunday when the call writes today's date.

The English `ahead of`, `beforehand` and `in advance` had the same effect until `_MOVES_DAY` read
them beside its `before`, `prior` and `eve`; the second draw below is that form.

Live, on the stack brain built from `d82ce5a12`, on a Sunday, every card approved
([readings](../../readings/schedule-one-time-weekday.md#audit-draws-on-the-refusal-2026-11-08)):

| Message | First call | After the refusal |
| --- | --- | --- |
| `Remind me at 6pm to put the bins out for Monday's collection.` | `at` 2026-11-08T18:00, refused | stored 2026-11-09 18:00, a day late |
| `Remind me at 6pm the evening ahead of Tuesday's dentist appointment.` | weekly, `on_days` `["mon"]`, refused by the weekly reader; then `at` 2026-11-09T18:00, refused | no reminder stored: the turn ended at the round cap |

The refusal names "the Mondays on either side" and asks for the call "on the Monday the person
meant", so the model moves a correct reminder onto the named day. A tool refusal keeps the tool
when unsure, so the form is on the unsafe side.

## What to do

1. Write the rows and a pass rule in `docs/readings/schedule-one-time-weekday.md` before any
   draw, with the first message above and its French and German forms.
2. Pass the turn's current date in the person's zone to the check and never refuse an `at` dated
   today. Write near misses first: "Remind me Tuesday evening at 7" with a Monday date must
   stay refused.
3. Draw the rows on a second brain beside a start-hash build.

## History

- 2026-11-08: filed by the night's audit slot, from two live draws and a unit probe; the same
  slot made `_MOVES_DAY` read `ahead`, `beforehand` and `advance`.
