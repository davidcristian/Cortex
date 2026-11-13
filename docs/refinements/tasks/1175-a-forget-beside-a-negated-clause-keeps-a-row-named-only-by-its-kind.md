# A forget beside a negated clause keeps a row named only by its kind

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-13

Over `User: Merke dir, meine Telefonnummer ist 0721 555 019.`, `Forget my phone number, I don't
need it anymore.` with call text `0721 555 019` keeps the row with `KEPT_ALL`, from the calling
chat and a new one, at the start build `cec7c748f` and at HEAD. `read_kinds` (`forget_kinds.py`)
stops a kind word listing a row when any clause of the message holds a negation, so the `don't`
of the second clause stops `phone` naming `Telefonnummer` in the first. The same message lists an
English phone row through the word `phone` itself. The row stays in memory and the kept note names
it, so nothing is lost; the forget the person asked for does not happen.

## What to do

1. Write the case as tests with near misses: `N'oublie pas ma carte.` and `Don't forget my phone
   number.` list no row by its kind.
2. Read the negation per clause, so a kind word lists a row only from a clause holding no negation
   and no word for minus, then replay the recorded forget strings.

## History

- 2026-11-13: filed from the review of the kind word replay, task
  [1158](1158-a-forget-in-one-language-keeps-a-row-stored-in-another.md).
