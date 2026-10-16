# A one-time request with a bare time is stored as a daily rule

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0065](../../adr/ADR-0065-wall-clock-schedule-times.md)
**Verified:** 2026-10-16

Asked for one time with a time of day and no repeat word, the cortex sometimes calls
`schedule_task` with `at_time`, which stores a daily rule, and replies as if it were one time. A
live turn on the real shell, "Remind me today at 23:00 to check the oven.", stored a daily rule
and replied "I've set a reminder for you to check the oven today at 23:00." With a fixed clock and
no history, "Remind me at 23:00 to check the oven." wrote `at_time` in 2 of 10 draws, "Remind me
at 2:55 to check the oven." in 2 of 5, and "Remind me today at 23:00 ..." in 0 of 10
([readings](../../readings/schedule-time-edges.md#t4-cortex-draws-under-a-fixed-clock)).
The earlier change to the `at` and `at_time` descriptions measured requests naming "tomorrow"
([readings](../../readings/schedule-one-time-and-daily.md)), not a bare time.

## Reproduction

`slot7/flow4.py E 10` and `B 5` in the 2026-10-16 run's scratch directory, against the cortex
server at 127.0.0.1:8080, and the live turn above through `slot3/ask.sh`.

## What to do

Prefer a typed result text over a description rule. Candidate: when `at_time` was given with no
day selector, the confirmation says the item repeats every day and that a one-time request is
made with `at` instead, so the model can correct itself with `edit_scheduled` or say it repeats.
Write the rows and the pass rule into the readings first: rows B, D and E with 20 draws each and
the live-shaped turn with history, plus the earlier readings' rows D and E ("every day", "every
Monday"), which must still store a rule. It ships only if no one-time row ends with a daily rule
the reply does not name.

## History

- 2026-10-16: filed from the time edge flows on the shared stack.
