# Dead-letter inspection

**Status:** landed 2026-07-12
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

Recorded in the [ADR-0025 dead-letter addendum](../../adr/ADR-0025-scheduling-reminders.md).
`RedisScheduleStore.dead_letters()`/`purge_dead_letter()`, adapter-only by design (the
quarantine is a codec mechanic the fake can never produce; a port method would force a
vacuous fake), operator-facing and never a model tool (the raw bytes are the content the
codec refused); runbook recipe + redis-cli equivalents in scheduling.md. Automated
retention stays deferred until quarantine volume ever exists.
