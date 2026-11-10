# The weekly stored note reads a repeat only in English

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0065](../../adr/ADR-0065-wall-clock-schedule-times.md)
**Verified:** 2026-11-10

`weekly_stored_notes` in `schedule_weekly_stored.py` shows `WEEKLY_STORED_NOTE` unless
`names_repeat` reads a repeat in the reply, and its own weekly patterns (`every Wednesday`, `on
Wednesdays`, `weekly`) are English only. A probe on 2026-11-10 (`slot19/probe2.py` in the run's
scratch directory) returned the English note under `Ich erinnere dich jeden Mittwoch um 9 Uhr.`,
a reply that already states the repeat. The note itself is English in every language, as
`FIRST_FIRE_NOTE` is.

## What to do

1. Count first: draw a weekly request in French, German, Spanish and Romanian on the stack and
   count the replies that state the weekly repeat.
2. Write near misses as tests first: a weekday named once (`am Mittwoch`), a question, and a
   negated repeat in each language.
3. Read `jeden Mittwoch`, `mittwochs`, `chaque mercredi`, `tous les mercredis`, `cada miércoles`,
   `los miércoles` and `în fiecare miercuri` as a repeat. The note's translations are a wording
   pick in another language, so they stay a proposal here.

## History

- 2026-11-10: filed by the third audit of the night's notes.
