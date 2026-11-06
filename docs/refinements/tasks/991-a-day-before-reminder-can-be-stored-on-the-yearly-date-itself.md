# A day-before reminder can be stored on the yearly date itself

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-06

For "Note that my mother's birthday is on 1 January, and remind me the day before." two of fifteen
draws stored a yearly rule on 01-01, the birthday itself, one of them beside the right 12-31
([readings](../../readings/schedule-yearly-month-before.md#the-next-row-2026-11-06)). The reminder
then fires on the day, not the day before. The typed check of R-981 reads only the refused
month day in the named month, so it does not catch this date.

## What to do

1. Write the rows and a rule into the readings first: the B03 request and other day-before
   requests, scored by whether a stored `on_dates` entry equals the named date itself.
2. Then try a typed check that refuses a stored entry equal to the named date when the message
   asks for a reminder before it, and draw the candidate on the same rows.

## History

- 2026-11-06: filed from the next-row draws of R-981.
