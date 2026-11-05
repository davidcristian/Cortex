# The yearly date refusal turns a monthly request with a start date yearly

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-05

`names_yearly_date` (`schedule_yearly.py`) reads any day of a named month in a message with no
month word as a yearly date, so the first `schedule_task` call with `on_month_days` is refused as
`YEARLY_DATE` on a real monthly request that also names a start, an end or another date. The
refusal text then gives the `on_dates` form, and the cortex stores a yearly rule. Both draws on
2026-11-05 did this: "Remind me to pay the gas bill on the 15th, starting 15 June." stored 06-15
yearly, and "Starting May 1, remind me on the 1st to pay rent." stored 05-01 yearly
([readings](../../readings/schedule-yearly-dates.md#monthly-requests-with-a-named-date-2026-11-05)).
The reply says "every year", so the person can see it, but a rent reminder then fires once a year.

The reader also matches "until Dec 10", "I'm away until June 2", "like Anna did on 3 March" and
the modal "I may 2" beside a monthly request. The rows that fixed the rule (M01, M02) both hold a
month word, so no row covered this.

## What to do

1. Write near-miss rows into the readings first: monthly requests that name a day with no month
   ("on the 15th", "on the 1st") beside a named date and no month word, scored monthly or not.
2. Then try a reader that does not refuse when the message also names a day with no month, or a
   refusal text that tells the model to keep `on_month_days` when the person asked for a day of
   every month, and draw both the near-miss rows and the Y rows of the readings.

## History

- 2026-11-05: filed from the closing audit's real turns on the build of the yearly date refusal.
