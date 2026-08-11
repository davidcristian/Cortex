# The display-timezone knob

**Status:** landed 2026-07-14
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

Recorded in the [ADR-0025 display
addendum](../../adr/ADR-0025-scheduling-reminders.md). `CORTEX_SCHEDULE_TZ` (an IANA key,
default `UTC`, passed through by `docker/docker-compose.yml` so it is not inert in the
container) is the zone `schedule_task` / `list_scheduled` / `snooze_scheduled` render in and
the zone an offset-less `at` is read as. A pure `DisplayZone(name, tz)` in the core carries
`render` + `resolve`; the IANA lookup stays at the composition root, so the core never
imports `zoneinfo`, and an unknown key fails the process at **boot** rather than at the first
listing. The two hardcoded `(UTC)` spec strings now name the configured zone, since correct
numbers under a false label would be worse than no knob. Two things implementation corrected
in this entry's own framing: reading a naive `at` as zone-local is a **deliberate behavior
change** (v1 rejected it, which was right only while everything rendered UTC), and rendering
needed a normalization hop through UTC, because `astimezone` returns `self` when the input
already carries the target zone and so printed a *nonexistent* wall time for a spring-forward
gap while the same instant read back from the store printed the canonical one. Display only:
stored `due_at`/`anchor` stay UTC instants, no record or codec changed, no migration.
Remaining:

## Trail

- 2026-07-14: Recorded under the ADR-0025 display addendum. The backlog index's opening warning,
  that an entry's own cost estimate is a hypothesis rather than a finding, cites this entry as one
  of the four whose estimate misled planning: it bundled a knob together with a recurrence change
  that no existing field can express. That warning carries no date of its own in the index, so the
  date on this line is the addendum's rather than the audit's.
