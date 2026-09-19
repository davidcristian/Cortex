# Cron expressions

**Status:** declined 2026-08-18
**Area:** scheduling
**Origin:** [ADR-0065](../../adr/ADR-0065-wall-clock-schedule-times.md)

Recorded inside the calendar-recurrence entry, which rejected cron for its first shape and left
this as its one remainder: a parser dependency, and a syntax a small model gets subtly wrong in
ways that still validate.

Declined, because both reasons still hold and a third has appeared:

- The parser is still a dependency or roughly 150 lines of pure core serving one field, and the two
  modules it would join are at 277 and 280 lines against a 300-line cap
  ([schedule_day_args.py](../../../brain/packages/core/src/cortex_core/schedule_day_args.py),
  [schedule_verbs.py](../../../brain/packages/core/src/cortex_core/schedule_verbs.py)), so cron
  forces splits before it parses anything.
- The authoring model still writes the field. `0 9 * * 1-5` validates while meaning something other
  than what was intended, and the day-selector design deliberately went the other way, into
  separate named fields with correction strings, because a small model mixes vocabularies inside
  one polymorphic field.
- Cron does not satisfy its own trigger. The trigger is "a rule the calendar shape cannot express
  turns up", and the likeliest such rule for a personal assistant is an nth or last weekday of the
  month. POSIX cron cannot write that either; it needs the Quartz `L` and `#` extensions. Adopting
  cron would buy the parser and leave the trigger open.

The shape has instead grown three times with no codec version bump. `MonthDays`, `YearDays` and the
per-rule zone were all added to the closed `DaySelector` union and the variant-by-key encoding that
reads it ([schedule_selectors.py](../../../brain/packages/core/src/cortex_core/schedule_selectors.py),
[schedule_codec.py](../../../brain/packages/session/src/cortex_session/schedule_codec.py)).

Two shapes remain inexpressible, and neither needs an entry, because both are additive under the
decision that closed the union. A rule fires at exactly one hour and minute, so "08:00 and 20:00"
needs two items where cron writes one expression; and `every` is a zone-blind interval, so "every
30 minutes between 09:00 and 17:00 on weekdays" has no shape at all. The first would widen
`CalendarRule` to a set of times, the second would add a fourth union variant. Nothing in the tree
asks for either.

## History

- 2026-07-14: Recorded as the calendar-recurrence entry's one remainder.
- 2026-07-15: The per-rule timezone was added and left this as the only calendar remainder, since a
  per-rule daylight-saving override is not owed.
- 2026-08-09: A review of the entries deferred until they cause a problem found that none had.
- 2026-08-18: Declined, on the findings above. The decisive new one is that POSIX cron cannot
  express the nth or last weekday of a month, which is the rule this entry was waiting for.
