# A duration in hours and minutes reads as a clock time in a reminder reply

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0065](../../adr/ADR-0065-wall-clock-schedule-times.md)
**Verified:** 2026-11-07

`names_time_of_day` (`schedule_claim.py`) reads `\d{1,2} ?h ?[0-5]\d` as a clock time unless
`in ` or `dans ` comes before it, and `limit_notes` then leaves out `STORED_TIME_NOTE`. A
duration written the same way is read as a time, so a reminder reply that names how long
something lasts and no time of day gets no note naming the stored time. Each of these returns
true:

- `La réunion dure 2h30.` (the comment above the bare hour form names `dure 2h` as a duration)
- `Le trajet prend 1h30, je te le rappelle demain.`
- `en 2h30`, `pendant 1h30`, `toutes les 2h30`, `para 1h30`

`dans 24h`, `d'ici 2h`, `in 2h`, `en 24h` and `within 24h` already return false.

## What to do

1. Write the forms above as tests first, beside `test_schedule_stored_time.py`.
2. Read the hour and minute form as a time only after a word for a point in time, as the bare
   hour form already is (`à`, `vers`, `um`, `gegen`, `a las`, `at`), or
   leave it out after `dure`, `prend`, `en`, `pendant`, `toutes les` and `para`.

## History

- 2026-11-07: filed by the audit of the readers of a French or German clock time in a reminder
  reply.
