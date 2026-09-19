# Edit verbs

**Status:** done 2026-07-13
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

Decided in [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md) decision 9. Changing an item's
text or its recurrence no longer needs cancel and recreate: one new fenced
`ScheduleStore.edit(item_id, edit)` transition (a plain watched `SET`, since only the record
changes and `due_at` stays put, so the indexes need no write) plus the fifth cortex-only built-in
`edit_scheduled(id, text?, every_seconds?)`. A `ScheduleEdit` value is applied by one pure
`apply_edit` both stores share. `every_seconds` has three cases: a bounded interval sets it, `0`
stops it, and omitting it leaves it alone. Changing the recurrence affects only future
rescheduling, because the next occurrence never moves.

The point the deferral made still holds: unlike cancel and snooze, the editing turn's taint is ORed
onto the item and never cleared, so the listing marks it and re-marks it, and a task cannot be
edited on a tainted turn at all, matching the refusal on creation, while a reminder edit under
taint is allowed. Contract-tested on the fake, on fakeredis and in the live Redis suite at 100%
covering retext, setting and clearing recurrence, taint monotonicity, the FIRING and unknown-item
refusals, and the WATCH-fence race.
