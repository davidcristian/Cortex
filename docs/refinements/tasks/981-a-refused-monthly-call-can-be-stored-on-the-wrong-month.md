# A refused monthly call can be stored on the wrong month

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-05

After the `YEARLY_DATE` refusal (`schedule_yearly.py`), the cortex makes the call again with
`on_dates`. For "Our wedding anniversary is on 3 September. Remind me a week before." one of
seven refused draws stored `on_dates` ["09-27"]: the day of the refused monthly call (27) in the
anniversary's month (September), where a week before 3 September is 08-27. The reminder then
fires once a year on the wrong day. No baseline yearly draw stored a wrong date
([readings](../../readings/schedule-yearly-dates.md#the-yearly-date-refusal-2026-11-05)).

## What to do

1. Write rows and a rule into the readings first: Y02 and other requests whose reminder falls in
   the month before the named date ("a week before 3 September", "two days before 1 March"),
   scored by whether the stored MM-DD equals the wanted date.
2. Then try a refusal text that names the date the reminder fires on rather than the named date,
   or a typed check that the stored `on_dates` entry is not the refused month day in the named
   month, and draw the candidate on the same rows.

## History

- 2026-11-05: filed from the candidate draws of R-951.
