# Yearly rules

**Status:** done 2026-07-14
**Area:** scheduling
**Origin:** [ADR-0065](../../adr/ADR-0065-wall-clock-schedule-times.md)

Decided in [ADR-0065](../../adr/ADR-0065-wall-clock-schedule-times.md) decision 3, as the union's
third variant and the last cycle a wall-clock rule can name. An annual occurrence (a birthday, a
renewal, a tax date) could only be written as a 365-day interval, which slips a full day every leap
year and never corrects itself, so the reminder moves off its own date within a decade.
`YearDays(days: frozenset[MonthDay])` joins `DaySelector`, offered to the model as `on_dates:
["12-25"]` on both `schedule_task` and `edit_scheduled`.

Three corrections to what the monthly design predicted, each found while writing the code:

- It predicted a `YearDays` variant naming a month alongside its days, but a single month with a
  day set cannot say "25 December and 1 January", which is the commoner annual shape. So it holds a
  set of `MonthDay(month, day)` pairs, whose natural sort order is chronological within the year;
  the walk and the codec both rely on that.
- The field is `on_dates`, not `on_year_days`, despite the symmetry with its two siblings, because
  "year day" already means the ordinal 1 to 366 and a small model reading it that way writes `[359]`
  for Christmas, which validates as something else.
- The description had to be shared, not just the parsing. Both verbs had their own copy of the
  selector JSON schema, so a third selector would have been a third difference between two
  descriptions of one vocabulary. `day_selector_properties()` now lives in `schedule_day_args.py`
  beside the parser that reads it. `at_time` stays per-caller, since its meaning really does differ
  between creation and edit.

Two policies are inherited rather than invented: 29 February moves to the 28th in a common year,
following the monthly clamp, and the walk stays total through the same `(candidates, wrapped)`
contract, with next year's earliest date as the fallback. A full ISO date is refused rather than
truncated, matching `at_time`'s refusal of a seconds field, since dropping the year silently would
answer a different question than the model asked; an unpadded `1-5` is accepted, because that is
unambiguous and drops nothing. The codec takes a third present-key variant (`year_dates`, as
`[month, day]` pairs), so both older variants still encode to the same bytes and no version bump or
migration is owed. `schedule_calendar.py` hit the 300-line cap and split, keeping the rule and the
occurrence math while `schedule_selectors.py` took the three selectors.

Tested at 100% line and branch coverage with the new checks proven by mutation, daylight-saving and
local-date cases on both sides of UTC, a four-occurrence no-slip property across the 2028 leap year,
and the codec's backward-compatible read tested against hand-written records from before the key
for both older variants, since the yearly key must fall through rather than take precedence.

The mutation pass corrected two things the 100% coverage did not, both worth reusing. The `>= start`
filter inside `walk` is an optimization rather than the strictness check, in the existing monthly
selector as much as the new one: removing either leaves the suite passing, because
`next_calendar_due`'s `instant > after` is the real test, so it is documented as a narrowing and
not claimed as proven. And the first attempt to mutate the full-ISO-date refusal (widening the
digit bound to `\d{1,4}`) left the suite passing, because what refuses `2026-12-25` is the
single-hyphen form, not the digit count, which `MonthDay`'s own validation would catch anyway.
Mutating toward the failure the check exists to prevent, a regex that truncates a leading year, is
what proved it.

Nothing remains by symmetry. A fourth variant would be a different kind of thing, an nth-weekday
rule such as "the second Tuesday".
