# Anchor-preserving occurrence snooze

**Status:** landed 2026-07-13
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

Recorded in the [ADR-0025 occurrence-snooze
addendum](../../adr/ADR-0025-scheduling-reminders.md). `snooze` now works on recurring items:
`ScheduledItem` gains an optional `anchor` (the recurrence grid origin, separate from `due_at`
the next fire; the separate-anchor field the edit verb deliberately did not add), one pure
`apply_snooze` both stores share pins it to the pre-snooze `due_at` on a recurring item's
first snooze, and the ticker re-arms from `recurrence_base(item)` so a snoozed series returns
to `origin + k*every` rather than drifting to `until + every`. The stores drop only the
recurring refusal (FIRING/unknown still answer `False`, fence untouched); `anchor` rides the
durable record as a forward-compatible additive key (no version bump, `decode` reads it with
`.get`); snooze still carries no taint gate (it injects no content). Contract-tested across
fake + fakeredis + the live Redis suite, plus pure `apply_snooze`/`recurrence_base` units, the
tool test, and a ticker test proving the anchor-grid re-arm, at 100%.
