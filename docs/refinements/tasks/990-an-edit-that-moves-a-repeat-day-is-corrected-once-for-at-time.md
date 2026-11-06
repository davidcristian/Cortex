# An edit that moves a repeat's day is corrected once for a missing at_time

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0065](../../adr/ADR-0065-wall-clock-schedule-times.md)
**Verified:** 2026-11-06

`parse_edit` in `schedule_verb_args.py` reads a day selector (`on_days`, `on_month_days`,
`on_dates`) only together with `at_time`, and corrects a call without it. In the day-only rows of
2026-11-06 ([readings](../../readings/schedule-day-only-times.md), row D6) every one of three
"Move that to the 20th." turns first called `edit_scheduled` with `on_month_days` [20] and no
`at_time`, read the correction, and called again with the stored `at_time` 09:00. The edit stored
the right rule each time, at the cost of a second model call per edit.

## What to do

1. Decide whether an edit that gives a day selector alone may keep the stored rule's wall-clock
   time (and zone). `parse_edit` sees no current item; the verb handler would read the item's
   rule before parsing and fill `at_time` from it when the item has a rule and the call gives a
   selector without one. An item with a fixed interval and no rule keeps the correction.
2. Tests first, the correction kept for the no-rule case, then redraw row D6 three times and
   count the calls per edit.

## History

- 2026-11-06: filed from the day-only rows.
