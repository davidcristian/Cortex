# Automated dead-letter retention

**Status:** open, fix when it bites
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Trigger:** quarantine volume ever exists.

Recorded inside the dead-letter inspection entry, which landed the operator-facing
`RedisScheduleStore.dead_letters()`/`purge_dead_letter()` pair and its runbook recipe.

Automated retention stays deferred until quarantine volume ever exists.

## Trail

- 2026-07-12: Recorded as the remainder when dead-letter inspection landed.
- 2026-08-09: A trigger sweep of the fix-when-it-bites bucket this entry sits in ran against
  the tree and fired nothing.
