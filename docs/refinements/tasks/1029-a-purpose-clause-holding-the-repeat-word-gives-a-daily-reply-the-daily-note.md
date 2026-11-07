# A purpose clause holding the repeat word gives a daily reply the daily note

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0065](../../adr/ADR-0065-wall-clock-schedule-times.md)
**Verified:** 2026-11-07

`_states_repeat` in `schedule_daily.py` removes `_ASIDE`, a purpose clause from `so you`, `pour
que`, `damit` or `para que` up to the next comma, before it looks for the repeat. When the reply
names the repeat inside that clause, the repeat is removed with it, and `DAILY_STORED_NOTE` is
appended to a reply that says the reminder repeats. Each reply below read as naming a repeat before
the aside was removed. A needless note is the safe direction.

Reproduction, unit level (`SCRATCH/slot20/probe2.py`, the reader before the change from `git show`):

| Reply | Before | Now |
| --- | --- | --- |
| "I set a reminder so you remember to take your pills every day." | repeat | none |
| "I'll remind you so that you take your pills daily." | repeat | none |
| "Je te le rappelle pour que tu prennes tes pilules tous les jours." | repeat | none |
| "Ich erinnere dich, damit du jeden Tag deine Tabletten nimmst." | repeat | none |

## What to do

1. Write the four rows as tests, beside the near misses the change was made for ("so you can",
   "so you don't forget").
2. Remove from the aside only its choice and negation words rather than the whole clause, or read
   the repeat in the whole sentence and the choice and negation in the sentence without the aside.

## History

- 2026-11-07: filed by the third audit of the night's changes.
