# ADR-0065: Wall-clock schedule times

**Status:** Accepted (2026-07-15)

## Context

[ADR-0025](ADR-0025-scheduling-reminders.md) stores a schedule's times as UTC instants and recurs an
item by a fixed `timedelta`. A user thinks in local wall time, so a reminder listed as `due
2026-07-22T18:00:00+00:00` reads wrong, and a fixed interval cannot follow the wall clock: a day is
23 or 25 hours long at a daylight-saving transition, so `every=1 day` fires an hour off twice a
year; a 30-day interval walks off the calendar every month; and a 365-day interval moves a day every
leap year and never corrects.

The core stays free of `zoneinfo`. Resolving an IANA key reads the system's tz database, which is an
impure step, so it belongs at the composition root and in adapters. A zone therefore reaches the
core as a value that already holds an abstract `tzinfo`.

## Decision

### 1. A display zone for every model-facing time

`CORTEX_SCHEDULE_TZ` (default `UTC`) is validated through `zoneinfo` when `ScheduleConfig` is built,
so a misspelt key such as `Europe/Bucarest` fails the process at startup with the key named. The
base `docker-compose.yml` passes it to the brain. The root resolves it into `DisplayZone(name, tz)`
(`cortex_core/schedule_time.py`, default `UTC_DISPLAY`), which the rendering built-ins and the
ticker share.

- **`render` is the one rendering of a model-facing time**, and the tool descriptions name the zone
  (`schedule_task` states the current time in it, `list_scheduled` labels due times with it). A
  label left as `UTC` over local numbers would state a false fact.
- **A naive `at` means wall time in the display zone.** Once the model reads local times it writes
  them back, and a refusal costs a round trip it may not recover from. An `at` with an offset is
  honoured as written.
- **`fold=0` settles the two irregular wall times**: an hour repeated at a fall-back transition
  takes the earlier offset, and an hour skipped at a spring-forward transition is read with the
  pre-transition offset, which puts it just past the gap.
- **`resolve` and `render` both normalize through UTC.** `datetime.astimezone` returns its input
  unchanged when the zone already matches, so a freshly resolved gap time rendered as a wall time
  that never occurs, while the same instant read back from the store rendered correctly. The
  creation confirmation and a later listing would have disagreed about one item.
- Stored times, the guarded state transitions and the interval arithmetic stay in UTC instants.

### 2. Calendar rules recur on the wall clock

`CalendarRule(hour, minute, on, zone)` (`cortex_core/schedule_calendar.py`) is a named wall time, a
day selector (decision 3) and an optional zone (decision 4). `next_calendar_due(rule, after, zone)`
returns the first occurrence strictly after `after`, and `next_occurrence` in `schedule.py`
dispatches between an interval and a rule. An item has one or the other, never both (ADR-0025
decision 2).

- **The first fire is derived from the rule.** `at_time` excludes `at` and `in_seconds`, a day
  selector without `at_time` is refused, and `every_seconds` with `at_time` is refused with the
  alternative named, so the model never has to keep a due time and a recurrence consistent by hand.
  An edit that sets a rule derives its next occurrence the same way (ADR-0025 decision 9).
- **Daylight saving is decided once**, by decision 1's `resolve`: an occurrence inside a gap fires
  just past it, late but never skipped, and one inside a repeated hour fires once. A reminder that
  silently does not happen is worse than one an hour late.
- **A rule is its own grid**, so a snoozed calendar item takes no `anchor` and returns to its
  cadence after the snoozed fire.
- **The ticker reads the deployment zone from `TickerSettings`**, the value the built-ins get,
  because setting the next occurrence is wall-clock arithmetic and must use the same zone that
  creation used.
- The creation confirmation and the listing share one recurrence phrase (`_recurrence` in
  `schedule_tools.py`), so they cannot describe one item differently.
- The record gains an added `rule` object, decoded with `.get` so an older record reads as having
  none; a rule that is present is decoded strictly, so a malformed one fails loudly rather than
  becoming a one-shot.

### 3. Day selectors: weekly, monthly and yearly

`on` is a closed union of three frozen values in `cortex_core/schedule_selectors.py`: `Weekdays`
(`date.weekday()` numbers; the default `DAILY` is all seven), `MonthDays` and `YearDays`, a set of
`MonthDay(month, day)` pairs, since annual dates such as 25 December and 1 January cluster across
months. `MonthDay` sorts chronologically within a year, which the search and the codec use.

- **A day the month lacks clamps to its last day; the month is never skipped.** `[31]` fires on 30
  April and on 28 or 29 February, and is how "the last day of the month" is said. 29 February fires
  on the 28th in a common year. A clamp that collides with another day fires once. Skipping would
  mean a reminder that silently does not arrive in some months, the worst outcome this feature has.
- **The search always terminates.** A selector is never empty, and each answers `walk(start)` with
  its window's dates from `start` onward plus one fallback in the next window, which is later by
  date and so later by instant in any zone. `next_calendar_due` has one body and no iteration cap. A
  rule walking past `date.max` ends the recurrence (`None`). The `>= start` filter inside `walk`
  saves resolutions; the strictness is enforced by `instant > after`.
- **The model writes three named fields**, mutually exclusive: `on_days` (weekday names),
  `on_month_days` (integers) and `on_dates` (`MM-DD`). A full ISO date is refused rather than
  truncated, since dropping the year would answer a different question. `on_dates` is not called
  `on_year_days` because a year day means the ordinal 1 to 366, and a model reading it that way
  writes `[359]` for Christmas.
- **One module owns the vocabulary.** `schedule_day_args.py` parses the day fields and holds their
  JSON-schema properties for both `schedule_task` and `edit_scheduled`, so the two verbs cannot
  describe it differently. `at_time` stays with each caller, whose meaning differs between them.
- **The codec tells variants apart by key**: `days`, `month_days` or `year_dates` (pairs as
  two-element arrays). A record without either newer key reads as weekly, and a weekly rule encodes
  as it always did.

The union is closed over the three cycles a wall-clock rule names. An nth-weekday rule ("the second
Tuesday") would be a different kind of selector.

### 4. A per-rule zone

A rule may have its own IANA zone, written as `in_zone` on `schedule_task` or `edit_scheduled` and
accepted only with `at_time`, since an interval has no wall clock to place. Without one the rule
follows `CORTEX_SCHEDULE_TZ`, so changing that setting moves those rules with the user, which is the
wanted meaning for an assistant that travels with one person.

- **In memory the rule holds a `DisplayZone`; the record stores only the name**, as an added `zone`
  key inside `rule`, written only when set.
- **Names are resolved through a `ZoneResolver` port** (`resolve(name) -> DisplayZone | None`). A
  per-rule zone comes from an open set, so it cannot be resolved once at startup; a name arrives
  only as model input or a stored record. The core's default is `UTC_ONLY_RESOLVER`; the root
  injects the `zoneinfo` resolver, passed with the default zone as one `ZoneContext`. An unknown key
  is a correction the model reads, not an enum on the tool description.
- **The codec resolves stored names itself** (`ZONEINFO_RESOLVER` in
  `cortex_session/zone_resolver.py`, the rule decoder's default argument), which keeps the resolver
  out of `RedisScheduleStore` and its call sites.
- **An unresolvable stored zone is a corrupt record** and fails loudly with the key and zone named.
  The boundary validates every name, so only a tz database change can produce one, and falling back
  to the deployment zone would fire the rule at a wall time nobody asked for.
- **A rule with a zone renders in that zone**: the confirmation, the listing and the edit result
  show `due_at` there, and `describe` appends the zone name, so the listing states which zone a bare
  wall time means.

## Consequences

- One daylight-saving policy serves a naive `at`, every calendar occurrence and every clamp: an
  irregular date or hour moves an occurrence and never deletes one.
- The brain image must include a tz database; `ZoneInfo` on an image without one fails every key but
  `UTC`. The slim Debian runtime image does include one.
- Tests resolve the daylight-saving cases against real `ZoneInfo` zones on both sides of UTC. A rule
  read against the UTC date instead of the local date is visible only west of UTC, where the UTC
  date is already tomorrow, so that direction is asserted.
- No record version bump or migration: `anchor`, `rule`, the selector keys and `zone` are all
  additions, and a record that does not use a newer capability encodes as before.
- Two times of day on one rule, or a wall-clock window on a sub-daily interval, have no form today.
  Each would be an addition: a set of times on `CalendarRule`, or a fourth selector.

## Alternatives rejected

- **Cron expressions.** A parser is a dependency or about 150 lines of pure core serving one field,
  a small model writes `0 9 * * 1-5` subtly wrong in ways that validate, and POSIX cron cannot
  express an nth or last weekday either, so it would not cover the rule most likely to be missed.
- **A `month_days` field beside the weekday set.** A monthly rule would have a weekday field it
  ignores, and "one selector per rule" would become a cross-field check instead of a shape.
- **One polymorphic `on_days`** taking names or numbers: a small model mixes the vocabularies.
- **A single `month` with a day set for yearly rules**: it cannot say 25 December and 1 January.
- **Skipping a month that lacks the day**, for the reason in decision 3.
- **A zone required on every rule**: the common single-zone case would write a key for nothing, and
  rules that should follow the user would stay behind.

## Related

- [ADR-0025](ADR-0025-scheduling-reminders.md) (the store, the verbs and the ticker these times
  feed), [brain-core](../modules/brain-core.md), [brain-session](../modules/brain-session.md),
  runbook [scheduling](../runbooks/scheduling.md).
