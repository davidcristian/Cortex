# A but after a word for all and a value opens no keep clause

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-15

Over the rows `Remember that my locker code is 4242.`, `Remember that my card is 4111 1111 1111
4242.` and `Remember that my phone is 0721 555 4242.`, with the call text `4242`, the message
`Forget all 4242 but the card.` deletes all three rows, the card included, which the message asks
to keep. `_opens_keep` (`forget_clauses.py`) reads `but` as opening a keep clause only right after
a word for all (`all but`), so here no keep clause opens and `quantifies` asks for every row. The
card lists the card row before the person approves, so they can decline, but the misread deletes a
row, which is not the card's safe direction. `Forget all but the card 4242.` keeps all three.

## What to do

1. Write tests first: the message above keeps the card row; `Forget all 4242 but quickly.` and
   `Forget every 4242 but do it now.` open a clause naming no row or none, and delete nothing more
   than today.
2. Read `but` after a word for all and then a value as opening a keep clause.
3. Replay every string literal of the brain's forget tests through the card before and after, and
   count rows newly deleted: there must be none.

## History

- 2026-11-15: filed while closing
  [task 1183](1183-a-forget-of-every-value-except-one-kind-keeps-a-row-of-another-kind.md), from a
  probe of the card, which that change leaves as it was.
