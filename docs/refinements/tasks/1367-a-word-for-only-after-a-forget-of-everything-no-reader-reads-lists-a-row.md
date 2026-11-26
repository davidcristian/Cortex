# A word for only after a forget of everything no reader reads lists a row

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-26

A word for only in a clause after a forget of everything keeps every row (`_kept_later` in
`forget_permit.py`), since `Forget everything, only the card.` can mean that the card stays. Over
750 mixed messages of the second audit of 2026-11-26 (`mixgen.py`, the `a2` scratch directory of
that run), 26 cases still list a row a reading keeps
([readings](../../readings/forget-form-cells.md#a-word-for-only-after-a-forget-of-everything-2026-11-26)):

- 24 after `Wipe`, which is no forget verb, so `everything` reads no forget of everything in
  `Wipe everything, only the card.` or `Wipe all of it, only the card.`;
- 2 in Romanian, `Uită tot, doar dulapul.` and `Șterge tot, doar dulapul.` with the call text
  `cardul`, where `_kept_later` is not reached.

## What to do

1. Find which reader lists the card in each form, and state one rule that keeps every row there.
2. Count over the generator and every other set the rows asked to delete it keeps, then draw it
   with the rows seeded.

## History

- 2026-11-26: filed when a word for only after a forget of everything was read as keeping every
  row.
