# A per-rule timezone

**Status:** done 2026-07-15
**Area:** scheduling
**Origin:** [ADR-0065](../../adr/ADR-0065-wall-clock-schedule-times.md)

Decided in [ADR-0065](../../adr/ADR-0065-wall-clock-schedule-times.md) decision 4. `CalendarRule`
gains an optional `zone: DisplayZone | None`, so a rule fires at its own wall clock (`in_zone:
"America/New_York"`) whatever `CORTEX_SCHEDULE_TZ` is, while a rule without a zone still follows
the deployment zone. A rule without a zone writes no `zone` key, so existing records are unchanged
and no migration is needed.

The cost the original one-line note missed is the resolver interface. A per-rule zone is an open
set, so unlike the single deployment zone it cannot be resolved once at boot. A `ZoneResolver` port
(UTC-only default in the core, the `zoneinfo`-backed `ZoneInfoResolver` injected at the root) is
needed wherever a name becomes a zone, and it reaches exactly three places: creation parsing, edit
parsing (a bad `in_zone` becomes a model correction), and the codec's decode, which resolves the
stored name itself so `RedisScheduleStore` and its five `decode` call sites stayed untouched
(threading a resolver through would have pushed `schedules.py` past the 300-line cap). An
unresolvable stored zone is a corrupt record and fails loudly, since it is reachable only through a
tz-database change and never through model input. An item with its own zone renders its `due_at` in
that zone, so the shown wall time matches the rule.

Two ruff limits (`PLR0911`, `PLR0913`) were hit and resolved by extracting a shared
`parse_calendar_rule`, which also removed the duplicate rule parsing between creation and the edit
verb, and by bundling the zone config into a `ZoneContext`, following the `TickerSettings`
precedent. Tested at 100% coverage with the two new checks proven by mutation (rule zone ignored,
unresolvable zone silently substituted; each makes a distinct test fail), and the codec round-trip
run on the fake, on fakeredis and on the live-Redis contract run.

A per-rule daylight-saving override is not owed, since the fold policy is inherited, so cron
expressions are the only calendar remainder.
