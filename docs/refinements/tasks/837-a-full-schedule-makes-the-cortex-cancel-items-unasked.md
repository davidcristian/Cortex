# A full schedule makes the cortex cancel items unasked

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-10-10

On 2026-10-10 the schedule held `CORTEX_SCHEDULE_MAX_ACTIVE` (32) items, most of them duplicate
"call Ana about the bulb payments" reminders left by measurement rows
([readings](../../readings/schedule-one-time-and-daily.md#results)). In a fresh chat, "Set a
reminder for tomorrow at 9:00 to call Ana about the bulb payments." ran `list_scheduled`, one
`schedule_task` call refused as full, then 13 `cancel_scheduled` calls, and no second
`schedule_task`. The reply read "I've noticed that there are already many reminders set for ...
I will go ahead and set the new one for you as well. OK. I've set a reminder for you ...". The
person asked for no cancel and was told none happened; every pending "call Ana" reminder from
earlier chats was gone afterwards, and no reminder from this turn was stored.

`cancel_scheduled` needs no confirmation, so nothing stopped the calls, and the full-schedule
result ("the schedule is full (32 active items); cancel one first") reads as an instruction the
model can follow itself.

## What to do

Decide whether the full-schedule result should tell the model to ask the user which item to
cancel, whether a cancel of an item the turn did not create should need a confirmation card, or
both, and check the false claim against the replay of tool runs. Measure before changing a text
the model reads: a schedule filled to the cap, then the reminder request, five repeats, counting
turns with a `cancel_scheduled` call and turns that claim a reminder with no successful call.

## History

- 2026-10-10: filed from the one-time and daily rows.
