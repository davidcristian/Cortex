# A word naming no row before the row a keep clause names again lists it

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-21

Over the rows `Remember that my locker code is 4242.`, `Remember that my card is 4111 1111 1111
4242.` and `Remember that my phone is 0721 555 4242.`, with the call text `4242`, `Forget the card
4242, keep only the card.` and `Forget the card 4242, keep my old card.` list the card. The first
message asks to keep it, and the second may. `_restated` (`forget_inside.py`) keeps a row named to
forget and again in a keep clause unless a word before its name in the clause names no row. That
condition deletes the card of `Forget the card 4242, I don't need the card.`, where `need` makes
the negation a request to delete, and `only` and `old` name no row either. The generator of 42,356
messages writes no such form, so its count of rows listed against the message has none of them.

## What to do

1. Write tests first: `keep only the card` keeps the card, and `I don't need the card` and `I
   don't want the card anymore` still delete it.
2. Add no word to a word list. Replay a shape that reads the words before the row name by the
   word opening the clause: after a keep verb or a word for except the row is kept whatever
   stands between, and after a negation only when every word between names a row. Count the rows
   it newly keeps that the message asks to delete, over the generator and every string of the
   brain's forget tests.
3. No row may be newly listed.

## History

- 2026-11-21: filed with the change that keeps a row a keep clause names again before a word
  naming no row
  ([R-1216](1216-a-keep-clause-naming-the-row-to-forget-beside-a-word-for-only-lists-it.md)).
