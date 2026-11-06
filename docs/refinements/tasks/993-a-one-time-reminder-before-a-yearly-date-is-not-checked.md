# A one-time reminder before a yearly date is not checked

**Status:** open, actionable
**Area:** tools
**Origin:** [ADR-0065](../../adr/ADR-0065-wall-clock-schedule-times.md)
**Verified:** 2026-11-06

`offset_date_wrong` (`schedule_offset.py`) reads only a `schedule_task` call with `on_dates`. The
model answers "remind me N days before" a yearly date with a one-time `at` as often as not: 1 of 4
B01 draws stored a one-time 2027-08-27
([readings](../../readings/schedule-yearly-month-before.md#the-typed-check-on-a-candidate-brain-2026-11-06)),
and the closing audit's turn "My sister's birthday is 14 February, remind me three days before"
stored `at: 2027-02-11T09:00:00Z`
([readings](../../readings/schedule-yearly-month-before.md#a-combined-turn-on-the-stack-brain-2026-11-06)).
Such a call stores the right date today, but one on the wrong date runs unchecked, and the reminder
fires once and never again with the yearly event.

Decide whether the check also reads the MM-DD of a one-time `at` against `wanted_dates`, and whether
a one-time `at` for a request that names a yearly event is itself refused toward `on_dates`, so the
reminder repeats. Write the near misses (a one-time request that names a birthday in passing) as
tests first, replay every recorded message, and draw the B rows and this turn's row on a rule
written before the run.

## History

- 2026-11-06: filed by the closing audit after the combined turn stored a one-time item.
