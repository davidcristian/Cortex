# The weekday refusal moves a reminder for the day after an event

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-08

`weekday_mismatch` in `schedule_weekday.py` refuses a one-time `at` the day after the one weekday
the message names, unless a word in `_MOVES_DAY` moves the day. A weekday that names an event
the reminder follows, with no such word, is still refused, and the refusal asks for the named day:
`Remind me at 9 to follow up on Monday's call.`, `Remind me to pay Tom back once Monday's payday
has cleared, at 9.` and `Remind me post Monday at 9 to rest.`, each with `at` Tuesday 09:00, are
refused on a Sunday. The test list refuses the same shape on purpose for `Remind me at 6pm to put
the bins out for Monday's collection.`, where the day after is the wrong date, so a possessive
weekday alone does not tell the two apart.

## What to do

1. Draw the three messages above and the bins message on the stack, and count where the first
   call and the retry put the date.
2. Compare a shape that reads the event's verb (`follow up`, `cleared`) against leaving the form
   refused. The safe direction is that a refusal never moves a correct reminder.

## History

- 2026-11-08: filed by the second audit of the night's changes, from unit probes; the same audit
  added `afterwards`, `next morning`, `is over`, `has passed` and `matin suivant` to `_MOVES_DAY`.
