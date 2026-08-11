# A per-rule timezone

**Status:** landed 2026-07-15
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

Recorded in the [ADR-0025 per-rule
addendum](../../adr/ADR-0025-scheduling-reminders.md). The calendar addendum recorded this as the
additive extension it turned out to be: `CalendarRule` gains an optional `zone: DisplayZone |
None`, so a rule fires at its own wall clock (`in_zone: "America/New_York"`) regardless of
`CORTEX_SCHEDULE_TZ`, while a zone-less rule still follows the deployment zone (the "your 09:00
follows you" default, byte-for-byte unchanged and no migration, since a zone-less rule writes
no `zone` key). The cost the calendar addendum's one-line note understated is the **resolver
seam**: a per-rule zone is an *open* set, so unlike the single deployment zone it cannot be
pre-resolved once at boot, and a `ZoneResolver` port (UTC-only default in the core, the
`zoneinfo`-backed `ZoneInfoResolver` injected at the root) is needed wherever a name becomes a
zone. It reaches exactly three boundaries: creation and edit parsing (a bad `in_zone` is a
model correction), and the codec's decode, which **self-resolves** the stored name so the
`RedisScheduleStore` and its five `decode` call sites stayed untouched (threading a resolver
through would have pushed `schedules.py` past the 300-line cap). An unresolvable *stored* zone
is a corrupt record (fail loud, only reachable via a tz-database change, never model input),
and a per-zone item renders its `due_at` in its own zone so the shown wall time matches the
rule. Two ruff ceilings fell out (`PLR0911`/`PLR0913`), resolved by extracting a shared
`parse_calendar_rule` (which also deduped creation/edit rule parsing) and bundling the zone
config into a `ZoneContext`, the `TickerSettings` precedent. CI-gated at 100% with the two new
guards mutation-proven (rule-zone ignored, unresolvable-zone silently substituted; each turns a
distinct test red), the codec round-trip run on fake + fakeredis + the live-Redis contract leg.
Remaining: a **per-rule DST-policy override** is not owed (the fold policy is inherited), so
only **cron expressions** stay open, as every calendar entry left them.
