# A request to remember can call the schedule tool

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-10-30

`schedule_task` shows no card: a call that validates stores the reminder at once. In the no-call
check's candidate draws
([readings](../../readings/forget-request-wordings.md#a-check-of-the-no-call-case-the-candidate-2026-10-30)),
two of 32 requests to remember called it. "Note that my mother's birthday is on 12 May." made the
cortex store a yearly reminder, `Mother's birthday` at 09:00 on 12 May, and reply "I've noted that
your mother's birthday is on May 12th and scheduled a reminder for you every year at 9:00 AM on
that date." The person asked for no reminder. "Please remember this: my brother's name is Luca."
called it with the text "The user's brother's name is Luca." and no time, which failed, so
nothing was scheduled. The other draw of the birthday row asked whether to set a reminder, which
is the behaviour a request to remember should have.

## What to do

1. Write rows and a rule into the readings before drawing a baseline: R01 to R15, four draws
   each, on a stack with schedules on, and a draw fails when its turn calls `schedule_task`.
2. Weigh a typed check over a description sentence: a `schedule_task` call on a turn whose
   message asks for no reminder, task or time, read in English the way `asks_not_kept` reads a
   message, is refused with a result telling the model to ask first. A refusal must not stop a
   request such as "Remind me at 9 to call my mother", so those rows go beside R01 to R15.

## History

- 2026-10-30: filed from the no-call check's candidate draws (R-923), where 2 of 32 requests
  to remember called it and one stored a reminder.
