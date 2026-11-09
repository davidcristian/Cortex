# An edit that sets repeat on a repeating rule says it now repeats

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-09

`made_repeating_after` in `schedule_made_repeating.py` records any `edit_scheduled` call with
`repeat`, `at_time` and a day selector, and `once_kept` refuses nothing when `repeat` is set, so an
edit of a daily rule to weekdays that sets `repeat` ends with `(This reminder now repeats. Ask to
make it one time again ...)`, about an item that never was one time. Two live draws of that form
on 2026-11-09 did not set `repeat`
([readings](../../readings/schedule-edit-repeat.md#second-audit-probes-2026-11-09)).

## What to do

Have the edit's result say whether the item was one time before it ran, as `ToolResult.forgot`
does for a forget, and record the item only then. Test with a fake store holding a daily rule.

## History

- 2026-11-09: filed by the second audit of the night's forget and schedule fixes, from unit probes.
