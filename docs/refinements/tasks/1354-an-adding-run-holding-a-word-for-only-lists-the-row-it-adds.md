# An adding run holding a word for only lists the row it adds

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-26

The forget card reads a run after the value that opens with an adding word or a word for and as
an addition (`run_role` in `forget_clauses.py`), even when it also holds a word for only, so
`Forget 4242, also the card only on the phone.` and `Forget 4242 and the card only on the phone.`
delete the card, which the generator marks as not asked for. Over the generator, English lists
64 rows not asked for in this form, and filling `seulement` or `nur` lists 56 and 22 more in the
same form ([readings](../../readings/forget-form-cells.md#a-word-for-only-read-as-a-limit-beside-another-clause-2026-11-26)).

## What to do

1. Write near misses as tests, then read such a run as a role no reader reads, so every row the
   words before the value do not name is kept. Count over the generator the rows asked to delete
   that it keeps.
2. Then take up [task 1326](1326-a-word-for-only-is-read-by-the-forget-card-in-english-alone.md).

## History

- 2026-11-26: filed from [task 1326](1326-a-word-for-only-is-read-by-the-forget-card-in-english-alone.md), whose cells list rows in this form once the rest of a word for only is read.
