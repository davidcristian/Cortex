# A list of names before a stays clause needs a seeded live draw

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-25

`kept_again` (`forget_clauses.py`) reads a clause holding only names of rows, just before a run no
reader reads or a keep clause naming its row before the keep verb, as a list that run or clause
ends, so `Forget 4242, the card, the phone stays.` keeps both rows
([readings](../../readings/forget-readers-seeded-draw.md#a-list-of-names-before-a-stays-clause-2026-11-25)).
The change was checked by replays of strings only. A change to what a reader lets the card list is
drawn live with the rows seeded, and on the core before the change the first form deleted the card
in 7 of 8 draws.

## What to do

1. Write the pass rule first: no approved card lists or deletes a row of the list or the stays
   clause; a row asked to delete that stays stored is a cost.
2. Draw `Forget 4242, the card, the phone stays.`, `Forget 4242, the card, the phone, the locker
   stays too.` and `Vergiss 4242, die Karte, das Handy bleibt.` 8 times each on the stack brain
   built from the tree, the three rows of the language seeded, every card approved.

## History

- 2026-11-25: filed when the list reading was added to `kept_again`.
