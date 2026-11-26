# A forget of every value beside a keep clause naming a row of no kind keeps every row

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-26

A forget of every value followed by a keep clause naming a row that is no kind of the card and
phone table keeps every row, the rows it asks to delete too: `Forget all 4242, not the locker.`,
`Oublie tous les 4242, pas le casier.` and `Vergiss alle 4242, nicht den Spind.` keep the card
and the phone holding `4242` as the last group of a longer value. `_beside_keep` in
`forget_unnamed.py` lists such a row only when `_other_kinds` reads each kept word as a kind word,
and `locker`, `casier` and `Spind` are none. Over the negated messages
(`~/.cache/cortex-run/2026-11-24/a3/`), these forms keep 546 of the 576 rows they ask to delete.
The direction is cost: the rows are kept.

## What to do

1. Find a reading of these forms that lists the card and the phone without listing a row a
   message asks to keep, with no new word in a list.
2. Replay with `replay.sh`, `m25.sh` and `cmp.py` in `~/.cache/cortex-run/2026-11-26/f1/`: no row
   asked to keep newly listed, and state the rows asked to delete now deleted.

## History

- 2026-11-26: filed from [task 1342](1342-a-forget-of-every-value-beside-a-french-or-english-negated-keep-clause-keeps-every-row.md),
  whose step 1 found this reader.
