# Occurrence snooze that keeps the anchor

**Status:** done 2026-07-13
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

Decided in [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md) decision 8. `snooze` now works on
recurring items. `ScheduledItem` gains an optional `anchor`, the origin of the recurrence grid,
separate from `due_at`, which is the next fire. One pure `apply_snooze`, shared by both stores,
sets the anchor to the pre-snooze `due_at` on a recurring item's first snooze, and the ticker
reschedules from `recurrence_base(item)`, so a snoozed series returns to `origin + k*every` instead
of slipping to `until + every`.

The stores drop only the refusal of recurring items; FIRING and unknown items still return `False`
and the fence is unchanged. `anchor` is stored as an additive key that older readers ignore, so
there is no version bump and `decode` reads it with `.get`. Snooze still has no taint check,
because it adds no content. Contract-tested on the fake, on fakeredis and in the live Redis suite,
plus units for `apply_snooze` and `recurrence_base`, the tool test, and a ticker test showing the
reschedule from the anchor grid, at 100%.
