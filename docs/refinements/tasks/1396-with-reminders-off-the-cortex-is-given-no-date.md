# With reminders off, the cortex is given no date

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0065](../../adr/ADR-0065-wall-clock-schedule-times.md)
**Verified:** 2026-11-28

The only current date a cortex request holds is in the `schedule_task` description (`The current
date-time is ...`), so on compose defaults, where `CORTEX_SCHEDULE_BACKEND` is `none` and the tool
is not offered, the cortex does not know the date. On 2026-11-28 the message `שלום! 🙂 מה השעה
בטוקיו כשבתל אביב 12:00? 🌏🕛` ("what time is it in Tokyo when it is 12:00 in Tel Aviv") was drawn
three times on those defaults and three times with the schedule backend on
([readings](../../readings/plain-defaults-smoke-flows.md#8-a-right-to-left-message-with-emoji)).
Off, every reply said 18:00, the difference while Israel is on summer time. On, every reply said
19:00, the right answer for that date, and named winter time. A French reminder draw with the
backend off also wrote in its thought that it did not know today's date.

## What to do

1. Send the current date-time and the zone `CORTEX_SCHEDULE_TZ` names in every cortex request,
   apart from the tool list, for example as one sentence of the system message, and check the
   deep tier's request for the same gap, which this pass did not read.
   The date changes the request's first tokens once a day, so measure what that costs the
   prompt cache before choosing the place.
2. Write the rule first, then draw: this message and two more whose answer turns on the date (a
   weekday of a date this month, the days left in the month) eight times each with the backend
   off, before and after; it passes when every reply after names the right figure.

## History

- 2026-11-28: filed from the plain defaults smoke flows.
