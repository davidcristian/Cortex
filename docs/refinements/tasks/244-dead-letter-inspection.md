# Dead-letter inspection

**Status:** done 2026-07-12
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

Decided in [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md) decision 7.
`RedisScheduleStore.dead_letters()` and `purge_dead_letter()` are on the adapter rather than the
port, because the quarantine is a codec mechanic the in-memory fake can never produce, so a port
method would force an empty fake implementation. They are for the operator and are never model
tools, since the raw bytes are the content the codec refused. The runbook recipe and the
`redis-cli` equivalents are in `scheduling.md`. Automated retention stayed deferred and was later
declined ([245](245-automated-dead-letter-retention.md)).
