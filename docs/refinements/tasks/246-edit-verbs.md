# Edit verbs

**Status:** landed 2026-07-13
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

Recorded in the [ADR-0025 edit addendum](../../adr/ADR-0025-scheduling-reminders.md). Retext /
re-recur without cancel-and-recreate: one new fenced `ScheduleStore.edit(item_id, edit)` transition
(a bare watched `SET`, since only the record changes and `due_at` stays put so the indexes need no
write) plus the fifth cortex-only built-in `edit_scheduled(id, text?, every_seconds?)`, replaying
the snooze slice. A `ScheduleEdit` value applied by one pure `apply_edit` both stores share;
`every_seconds` is three-valued (a bounded interval sets, `0` stops, omission leaves), and re-recur
changes only future re-arms because the next occurrence never moves. The nuance the deferral named
holds: unlike cancel/snooze the editing turn's taint **ORs onto the item, never clears it** (so the
listing badges it and re-taints), and a **task** cannot be edited on a tainted turn at all (the
creation-side refusal), while a reminder edit under taint is allowed. Contract-tested across fake +
fakeredis + the live Redis suite (retext, set/clear recurrence, taint monotonicity, FIRING/unknown
refusal, the WATCH-fence race) at 100%.
