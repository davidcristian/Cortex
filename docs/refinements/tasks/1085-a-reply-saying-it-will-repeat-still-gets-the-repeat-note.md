# A reply saying it will repeat still gets the repeat note

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0065](../../adr/ADR-0065-wall-clock-schedule-times.md)
**Verified:** 2026-11-09

`_REPEATS` in `schedule_daily.py` reads `repeats` and `repeating` but not a bare `repeat`, so
`names_repeat` finds no repeat in `It will now repeat every Tuesday at 15:00.` and the reply also
gets `MADE_REPEATING_NOTE`; `DAILY_STORED_NOTE` reads the same sentence the same way. The note is
true, so the miss is on the reader's safe side, and the cost is a repeated fact
([readings](../../readings/schedule-edit-repeat.md#a-live-edit-asked-to-repeat)).

## What to do

1. Write near misses first: `It will not repeat.`, `Should it repeat?`, `If you want it to repeat,
   say so.` and a reminder text holding the word (`remind me to repeat the exercise`).
2. Read `will repeat` and `now repeat` as a stated repeat, and replay every reply recorded in
   `docs/readings/` through the old and new reader before shipping.

## History

- 2026-11-09: filed from a live edit that made a one-time reminder repeat on Tuesdays.
