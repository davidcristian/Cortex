# A forget of every value beside a French or English negated keep clause keeps every row

**Status:** done 2026-11-26
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

A forget of every value followed by a negated keep clause naming one row keeps every row in French
and English, the rows it asks to delete too: `Oublie tous les 4242, pas le casier.`, `Oublie tous
les 4242, n'efface pas le casier.`, `Forget all 4242, not the locker.` and `Forget all 4242,
don't delete the locker.` delete nothing for the call text `4242` or any row's word, while
`Vergiss alle 4242, nicht die Karte.` deletes the locker code and keeps the card. In the English
`don't` form, `don` is read in the part asking to forget as a word naming a fact
([readings](../../readings/forget-keep-any-reading.md#a-forget-verb-inside-a-keep-clause-2026-11-25)).

## What to do

1. Find which reader keeps the rows of `Oublie tous les 4242, pas le casier.` and `Forget all
   4242, not the locker.`, where the German form deletes the locker code.
2. Read `don` before `t` as a leading word of the keep clause, as `do` is, with no new word in a
   list.
3. Replay the generator, the audit's negated messages (`~/.cache/cortex-run/2026-11-24/a3/`) and
   the a1 word pairs: no row asked to keep listed, and state the rows asked to delete now deleted.

## History

- 2026-11-25: filed from [task 1336](1336-a-forget-of-every-value-beside-a-negated-forget-verb-keeps-every-row.md),
  whose German, Spanish and Romanian forms are now read.
- 2026-11-26: done. Step 1: `_beside_keep` in `forget_unnamed.py` keeps the rows. It lists a row
  holding the value as the last group of a longer value only when `_other_kinds` reads each kept
  word as a kind of the card and phone table, and `locker`, `casier` and `Spind` are none, so
  `Vergiss alle 4242, nicht den Spind.` keeps every row too; the German message above names the
  card. The kept row decides, not the language. Its count is
  [recorded](../../readings/forget-freeze.md#forms-left-unread-at-the-freeze-2026-11-26).
  Step 2: `parts` reads `don` before `t` in the keep clause, so `Forget all 4242, don't delete the
  card.` keeps the card alone, and 312 negated and 30 mixed builder rows asked to delete are now
  deleted, with no row asked to keep newly listed
  ([readings](../../readings/forget-keep-any-reading.md#a-contracted-negation-2026-11-26)).
