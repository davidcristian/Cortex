# Cron expressions

**Status:** declined 2026-08-18
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

Recorded inside the calendar-recurrence entry, which rejected cron for its first shape and left
this as its one remainder, and restated by the per-rule-timezone entry as the only calendar
remainder still open. Cron was rejected there on two counts: a parser dependency, and a syntax a
small model gets subtly wrong in ways that still validate.

**Declined, because both of those counts still hold and a third has appeared.**

**The parser is still a dependency or roughly 150 lines of pure core serving one field**, and the
two modules it would land beside are at 277 and 280 lines against a 300-line cap
([schedule_day_args.py](../../../brain/packages/core/src/cortex_core/schedule_day_args.py),
[schedule_verbs.py](../../../brain/packages/core/src/cortex_core/schedule_verbs.py)), so cron
forces splits before it parses anything.

**The authoring model still writes the field.** `0 9 * * 1-5` is still a syntax that validates
while meaning something other than what was intended, and the day-selector design deliberately went
the other way, into separate named fields with correction strings, precisely because a small model
mixes vocabularies inside one polymorphic field.

**The new count is that cron does not close its own trigger.** The trigger is "a rule the calendar
shape cannot express turns up", and the likeliest such rule for a personal assistant is an nth or
last weekday of the month. POSIX cron cannot write that either; it needs the Quartz `L` and `#`
extensions. Adopting cron would buy the parser and leave the trigger armed.

**What the shape has done instead is grow, three times, without a codec version bump.** `MonthDays`,
`YearDays` and the per-rule zone all landed as additions to the closed `DaySelector` union and the
variant-by-key encoding that reads it
([schedule_selectors.py](../../../brain/packages/core/src/cortex_core/schedule_selectors.py),
[schedule_codec.py](../../../brain/packages/session/src/cortex_session/schedule_codec.py)). That is
the extension path demonstrated rather than argued.

**The genuine residue, named so it is not lost.** Two shapes are inexpressible today and neither
needs an entry, because both are additive under the decision that closed the union: a rule fires at
exactly one hour and minute, so "08:00 and 20:00" needs two items where cron writes one expression,
and `every` is a zone-blind interval, so "every 30 minutes between 09:00 and 17:00 on weekdays" has
no shape at all. The first is a widening of `CalendarRule` to a set of times, the second a fourth
union variant. Nothing in the tree asks for either.

## Trail

- 2026-07-14: Recorded as the calendar-recurrence entry's one remainder, cron itself having been
  rejected there as a parser dependency and a syntax a small model gets subtly wrong in ways that
  still validate.
- 2026-07-15: The per-rule timezone landed and left this as the only calendar remainder, a per-rule
  DST-policy override not being owed.
- 2026-08-09: A trigger sweep of the fix-when-it-bites bucket this entry sits in ran against the
  tree and fired nothing.
- 2026-08-18: Declined on a re-derivation. The deferral was about the shape rather than the timing,
  and three landed extensions prove the other shape works; the decisive new finding is that POSIX
  cron cannot express the nth or last weekday of a month, which is the very rule this entry waits
  for. The residue above is additive under the closed-union decision and is recorded there rather
  than kept as an entry.
