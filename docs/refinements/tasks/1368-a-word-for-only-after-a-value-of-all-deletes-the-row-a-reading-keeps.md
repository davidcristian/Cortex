# A word for only after a value of all deletes the row a reading keeps

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-26

`Forget all 4242, only the card.` deletes the card and keeps the other rows: the word for only is
read as a limit (`alone` in `forget_only.py`). A reading "all 4242 goes, only the card stays"
keeps the card, the same reading that keeps every row of `Forget everything, only the card.`
([readings](../../readings/forget-form-cells.md#a-word-for-only-after-a-forget-of-everything-2026-11-26)).
Over the 240 cases of this form in the 750 mixed messages of the second audit of 2026-11-26
(`mixgen.py`, the `a2` scratch directory of that run), 48 delete the row the word for only names.

## What to do

1. Decide whether that reading is one the keep rule counts. If it is, keep every row in this form
   and count over the generator and every other set the rows asked to delete it keeps.
2. Draw the change with the rows seeded, and edit the ADR's example of this form.

## History

- 2026-11-26: filed when a word for only after a forget of everything was read as keeping every
  row.
