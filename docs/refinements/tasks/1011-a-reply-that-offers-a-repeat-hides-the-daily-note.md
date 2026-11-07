# A reply that offers a repeat hides the daily note

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0065](../../adr/ADR-0065-wall-clock-schedule-times.md)
**Verified:** 2026-11-07

`limit_notes` appends `DAILY_STORED_NOTE` when a turn left a daily item and `names_repeat(reply)`
(`schedule_daily.py`) is false. `names_repeat` searches the whole reply for any repeat word, so a
reply that asks whether the reminder should repeat, or offers to make it repeat, reads as saying
it repeats, and the note is left out. That is the reply the note exists for: one that implies a
single reminder while the stored item fires every day. Each of these returns true:

- `Reminder set for 8:00. If you want it every day, tell me.`
- `I'll remind you once at 8. Should it repeat?`
- `I'll remind you at 8 tomorrow; I can repeat this if you want.`
- `I'll remind you at 8 tomorrow. Repeat after me: water the plants.`
- `Te lo recordaré mañana a las 8. ¿Quieres que se repita cada día?`

Two replies that do say it repeats return false and get a correct but extra note:
`Te lo recordaré cada mañana a las 8.` and `Îți voi aminti zi de zi la 8.`

## What to do

1. Write the replies above as tests first, beside `test_schedule_daily.py`.
2. Read the reply per sentence, as `claims_chat_only` does: skip a question and a clause that
   opens with `if`, `si`, `wenn`, `falls` or `dacă`, and read `repeat` only as a statement about
   the reminder (`it repeats`, `repeating`), not the verb on its own.
3. Add `cada mañana`, `cada noche` and `zi de zi` to the forms that say it repeats.

## History

- 2026-11-07: filed by the audit of the note under a daily reminder whose reply names no repeat.
