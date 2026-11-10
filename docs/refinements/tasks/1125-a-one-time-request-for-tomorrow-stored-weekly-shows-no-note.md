# A one-time request for tomorrow stored weekly shows no note

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0065](../../adr/ADR-0065-wall-clock-schedule-times.md)
**Verified:** 2026-11-10

On 2026-11-10, `Remember that I park on level 3 and remind me tomorrow at 9 to move the car.`
(chat `s12-br2-4`) had its fan-out refused, then a `schedule_task` call without `kind` failed,
and the retry stored `at_time` 09:00 with `on_days` `["wed"]` and `starting` 2026-11-11: a rule
for every Wednesday. The reply said only "tomorrow at 9:00 AM", and no note named the weekly
repeat, since `DAILY_STORED_NOTE` reads daily items only and `weekly_unasked` refuses `on_days`
only when the message names one weekday
([readings](../../readings/schedule-daily-first-fire.md#results-2026-11-10)). 1 of 14 draws that
night; on the first build a weekly Thursday rule (r1-4) was named by its reply.

## What to do

1. Write the pass rule first: a reply over a rule on chosen days, stored this turn for a message
   naming no repeat word, ends with a note naming the repeat unless a sentence of the reply
   states one (`names_repeat`).
2. Build it as a brain-appended note beside `DAILY_STORED_NOTE`, with no refusal.
3. Draw the message above at least six times and count weekly stores and notes.

## History

- 2026-11-10: filed from the first fire draws on the shared stack.
