# Snooze

**Status:** landed 2026-07-12
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

Recorded in the [ADR-0025 snooze addendum](../../adr/ADR-0025-scheduling-reminders.md).
A new fenced `ScheduleStore.snooze(item_id, until)` transition (WATCH-fenced like
finish/release/ack, contract-tested across fake + fakeredis + the live suite) plus the
fourth cortex-only built-in `snooze_scheduled(id, for_seconds)` (in `schedule_verbs.py`,
the line-cap split that took `cancel_scheduled` along). It shipped one-shots only (a snoozed
recurring item would silently re-anchor its series), with the recurring case recorded as a
remainder; that **anchor-preserving occurrence snooze landed 2026-07-13** (its own entry
below). A fired-but-undelivered reminder re-arms (fires fresh, never re-delivers stale).
