# A one-time item for tomorrow stored for today may show no note

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0065](../../adr/ADR-0065-wall-clock-schedule-times.md)
**Verified:** 2026-11-10

On 2026-11-10 at about 05:12 local, two draws of `Read notes.txt and remind me tomorrow at 9 of
the first item in it.` stored one time at 09:00 today under a reply saying tomorrow (chats
`s12-r1-1` and `s12-r1-3`). r1-1 stored a daily item and then made it one time with
`edit_scheduled` and `every_seconds` 0; `FIRST_FIRE_NOTE` now names that case. r1-3's calls were
not logged after the brain was rebuilt, so whether it wrote `at` for today directly is not known.
A direct one-time `at` today is not read by `early_first_fire`, which reads `at_time` stores only
([readings](../../readings/schedule-daily-first-fire.md#results-2026-11-10)).

## What to do

1. Draw the message above at least eight times before 09:00 local, with the brain's
   `tool.invocation` lines kept, and count one-time `at` calls dated today.
2. If any came, write a pass rule and widen `early_first_fire` to a one-time store first firing
   before the named day, with near misses first (`in 10 minutes` beside a request for tomorrow).
3. If none came, decline with the counts.

## History

- 2026-11-10: filed from the first fire draws on the shared stack.
