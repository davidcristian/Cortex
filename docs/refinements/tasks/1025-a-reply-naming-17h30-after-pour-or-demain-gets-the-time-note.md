# A reply naming 17h30 after pour or demain gets the time note

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0065](../../adr/ADR-0065-wall-clock-schedule-times.md)
**Verified:** 2026-11-07

`names_time_of_day` in `schedule_claim.py` reads an hour written with `h` only after `à`, `vers`,
`um`, `gegen`, `a las` or `at`, so a duration such as "dure 2h30" is not read as a clock time.
French replies name a stored time after other words too, and each reply below now gets the note
giving the stored time, though it names that time. Each was read as naming a time before the
change:

| Reply | Word before the hour |
| --- | --- |
| "Rappel réglé pour 17h30." | `pour` |
| "Je te le rappelle demain 17h30." | `demain` |
| "C'est noté : rappel aujourd'hui, 17h30." | a comma |
| "Rappel programmé dès 17h30 demain." | `dès` |

Reproduction, unit level: `SCRATCH/slot16/probe.py` prints `old=True head=False` for each. A
needless note is the safe direction.

## What to do

1. Write the four rows as tests first, beside the durations the change keeps out ("dure 2h30",
   "pendant 1h30", "dans 2h30").
2. Read an `h` hour after any word except a duration word (`dure`, `pendant`, `dans`, `en`, `für`,
   `durante`, `timp de`), rather than only after a point word.

## History

- 2026-11-07: filed by the second audit of the night; reproduced at unit level, no turn sent.
