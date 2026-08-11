# Yearly rules

**Status:** landed 2026-07-14
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

Recorded in the [ADR-0025 yearly
addendum](../../adr/ADR-0025-scheduling-reminders.md). The union's designed third variant, and
the last cycle a wall-clock rule can name. An annual occurrence (a birthday, a renewal, a tax
date) had no expression but a 365 day interval, which is the worst case the rule shape
exists for: it drifts a full day every leap year and never self-corrects, so the reminder
walks off its own date within a decade. `YearDays(days: frozenset[MonthDay])` joins
`DaySelector`, model-facing as `on_dates: ["12-25"]` on both `schedule_task` and
`edit_scheduled`. **Three corrections to the monthly addendum's own framing, each found by
writing the code:** (1) it predicted "a `YearDays` variant naming a month alongside its
days", and a single month with a day set cannot say "25 December and 1 January", which is the
commoner annual shape, so it holds a set of `MonthDay(month, day)` pairs whose natural sort is
chronological-within-the-year (the walk and the codec both lean on that rather than
re-deriving it); (2) the field is **`on_dates`, not `on_year_days`**, despite the symmetry
with its two siblings, because "year day" already means the ordinal 1..366 and a small model
reading it that way writes `[359]` for Christmas, which validates as nothing; (3) the
advertisement, not just the parsing, had to be shared: both verbs carried their own copy of
the selector JSON schema, so a third selector would have been a third divergence between two
descriptions of one vocabulary, and `day_selector_properties()` now lives in
`schedule_day_args.py` beside the parser that reads it (`at_time` stays per-caller, its
meaning genuinely differing between creation and edit). Two policies are **inherited rather
than invented**: 29 February clamps to the 28th in a common year (the monthly clamp, which is
daylight saving's "an irregularity moves an occurrence and never deletes one"; skipping would
fire it in one year of four), and the walk stays total by the same `(candidates, wrapped)`
contract, its fallback being next year's earliest date. A full ISO date is **refused rather
than truncated**, matching `at_time`'s refusal of a seconds field, since dropping the year
silently would answer a different question than the model asked; an unpadded `1-5` is accepted,
because leniency there is unambiguous and drops nothing. The codec takes a third present-key
variant (`year_dates`, as `[month, day]` pairs), so both older variants still encode
byte-identically and no version bump or migration is owed. `schedule_calendar.py` hit the
300-line cap and split, keeping the rule and the occurrence math while `schedule_selectors.py`
took the three selectors, which is the union's own responsibility line. CI-gated at 100% line
and branch with the new guards mutation-proven, DST and local-date cases on both sides of UTC,
a four-occurrence no-drift property across the 2028 leap year, and the codec's
backward-compatible read tested against hand-written pre-addendum records for **both** older
variants (the yearly key must fall through, not shadow). **Two things the mutation pass
corrected that the 100% gate did not**, both worth reusing: the `>= start` filter inside
`walk` is an optimization rather than the strictness guard, in the **existing monthly**
selector as much as the new one (removing either leaves the suite green, since
`next_calendar_due`'s `instant > after` is the real test), so it is documented as a narrowing
and deliberately not claimed as proven; and the first attempt to mutate the full-ISO-date
refusal (widening the digit bound to `\d{1,4}`) stayed green because what refuses
`2026-12-25` is the single-hyphen *shape*, not the digit count, which `MonthDay`'s own
validation would catch anyway. Mutating toward the failure the guard exists to prevent (a
regex that truncates a leading year) is what proved it. Remaining: nothing by symmetry. A
fourth variant would be a different kind of thing (an nth-weekday rule, "the second Tuesday").
