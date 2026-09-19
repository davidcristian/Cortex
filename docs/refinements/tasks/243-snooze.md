# Snooze

**Status:** done 2026-07-12
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

Decided in [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md) decision 8. A new fenced
`ScheduleStore.snooze(item_id, until)` transition, WATCH-fenced like finish, release and ack, and
contract-tested on the fake, on fakeredis and in the live suite, plus the fourth cortex-only
built-in `snooze_scheduled(id, for_seconds)` in `schedule_verbs.py`, the line-cap split that took
`cancel_scheduled` with it. It covered one-shots only, because a snoozed recurring item would
silently move its whole series; the recurring case became
[247](247-anchor-preserving-occurrence-snooze.md), done 2026-07-13. A reminder that fired but was
not delivered fires fresh rather than re-delivering the stale one.
