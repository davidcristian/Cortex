# The display-timezone setting

**Status:** done 2026-07-14
**Area:** scheduling
**Origin:** [ADR-0065](../../adr/ADR-0065-wall-clock-schedule-times.md)

Decided in [ADR-0065](../../adr/ADR-0065-wall-clock-schedule-times.md) decision 1.
`CORTEX_SCHEDULE_TZ` (an IANA key, default `UTC`, passed through by `docker/docker-compose.yml` so
it reaches the container) is the zone `schedule_task`, `list_scheduled` and `snooze_scheduled`
render in, and the zone an `at` without an offset is read as. A pure `DisplayZone(name, tz)` in the
core provides `render` and `resolve`; the IANA lookup stays at the composition root, so the core
never imports `zoneinfo`, and an unknown key fails the process at boot rather than at the first
listing. The two hardcoded `(UTC)` spec strings now name the configured zone.

Two things differ from what this entry originally said. Reading a naive `at` as zone-local is a
deliberate behavior change: v1 rejected it, which was right only while everything rendered UTC.
And rendering needs a normalization step through UTC, because `astimezone` returns `self` when the
input already has the target zone, and so printed a nonexistent wall time for a spring-forward gap
while the same instant read back from the store printed the canonical one.

Display only: stored `due_at` and `anchor` stay UTC instants, no record or codec changed, no
migration.

## History

- 2026-07-14: Recorded under ADR-0065 decision 1. The backlog index warns that an entry's own cost
  estimate is a hypothesis rather than a finding, and cites this entry as one of four whose
  estimate misled planning: it bundled a setting together with a recurrence change that no existing
  field could express. That warning has no date of its own, so this line records the date of the
  change.
