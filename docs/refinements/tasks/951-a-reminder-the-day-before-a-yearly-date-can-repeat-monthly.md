# A reminder the day before a yearly date can repeat monthly

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-10-30

"Note that my mother's birthday is on 12 May, and remind me of it the day before." made the
cortex call `schedule_task` with a reminder due on the 11th of every month, first on 11 November,
and the reply said "on the 11th of every month"
([readings](../../readings/side-effect-tools-on-remember.md#the-candidate-2026-10-30)). The
three other draws of the row stored it yearly on 11 May. The reply names what was stored, so the
person can see it, but a birthday repeats yearly.

## What to do

1. Write rows and a rule into the readings before a baseline: requests for a reminder before a
   yearly date (a birthday, an anniversary, a renewal), drawn often enough to measure how many
   store a monthly or a one-time reminder.
2. If monthly reminders recur, weigh a sentence in the `schedule_task` description about yearly
   dates against a typed check of the message that reads a yearly date and a monthly rule.

## History

- 2026-10-30: filed from the candidate draws of the side-effect tools check (R-901).
