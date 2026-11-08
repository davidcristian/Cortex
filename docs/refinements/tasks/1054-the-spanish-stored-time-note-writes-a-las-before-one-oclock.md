# The Spanish stored time note writes "a las" before one o'clock

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0076](../../adr/ADR-0076-closing-note-language.md)
**Verified:** 2026-11-08

The Spanish text of `STORED_TIME_NOTES` in `schedule_claim.py` is `es a las {time}`, and `{time}`
is the stored `HH:MM`. Spanish writes the singular `a la` for one o'clock, so a reminder stored at
01:00 to 01:59 reads `a las 01:30`, which is not correct Spanish. Every other hour reads correctly,
and the French, German and Romanian texts take any `HH:MM`.

## What to do

1. Write `a la` when the hour is 01, or reword the Spanish note so it takes any time, and list the
   new text in the commit for the maintainer's review.

## History

- 2026-11-08: filed by the second audit of the night's changes.
