# Draw the head read after another forget clause with the rows seeded

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-26

`_kept_later` (`forget_permit.py`) reads a head, and the clauses after it, from each clause holding
a forget verb outside a keep clause, not only the first, so `Forget the card. Forget everything the
phone stays.` keeps the phone. The change was replayed over strings only
([readings](../../readings/forget-form-cells.md#a-head-after-another-forget-clause-2026-11-26)):
no row newly listed and no row asked to delete newly kept. A change to what a reader lets through
is drawn live with the prior state seeded before it is trusted.

## What to do

1. Write the pass rule first: rows `tmplen` seeded, every card approved, 8 draws per message, and
   a message passes when no row it asks to keep and no row it does not name is deleted.
2. Draw `Forget the card. Forget everything the phone stays.`, `Forget the phone, forget all of it
   the card stays.` and `Oublie le casier, oublie tout la carte reste.` on the stack, count with the
   seeded draw scripts of the `a2` slot in `~/.cache/cortex-run/2026-11-26/`, and write the rows
   into the readings.

## History

- 2026-11-26: filed when the head was read after another forget clause, replayed without a draw.
