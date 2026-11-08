# A repeat phrase in the reminder text hides the daily note

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0065](../../adr/ADR-0065-wall-clock-schedule-times.md)
**Verified:** 2026-11-08

`names_repeat` (`schedule_daily.py`) reads a phrase form such as `every morning`, `jeden Morgen`,
`chaque matin`, `cada mañana` or `în fiecare dimineață` as a repeat wherever it stands in a
clause, so a phrase inside the reminder's own text counts as saying the reminder repeats, and
`DAILY_STORED_NOTE` is left out over a daily item. `I'll remind you at 8 to take the pill you take
every morning.` returns true. The adjective forms were fixed on 2026-11-08 by reading them only
beside a word for the reminder; a phrase form is also how most replies state a real repeat ("I'll
remind you every morning at 8"), so the same window would add needless notes.

## What to do

1. Write the relative clause reply above and its German, French, Spanish and Romanian forms as
   tests, beside replies that state the repeat with the phrase after the time ("at 8 every
   morning").
2. Leave out a phrase that follows a relative pronoun or a second verb of the person (`you take`,
   `que tu prends`, `die du nimmst`), and replay every recorded reply through the old and new
   reader.

## History

- 2026-11-08: filed by the slot that fixed the adjective forms of
  [R-1018](1018-a-repeat-word-in-the-reminder-text-hides-the-daily-note.md); none of the 1,157
  replayed replies has the form.
