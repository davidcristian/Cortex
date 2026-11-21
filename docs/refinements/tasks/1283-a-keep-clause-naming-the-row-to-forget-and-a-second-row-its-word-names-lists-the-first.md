# A keep clause naming the row to forget and a second row its word names lists the first

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-21

Over the rows `Remember that my card is 4111 1111 1111 4242.`, `Remember that my new card is 5500
0000 0000 4242.` and `Remember that my locker code is 4242.`, with the call text `4242`, `Forget
the card 4242, keep the card and my new card.` lists the first card, which the message asks to
keep. `_restated` (`forget_inside.py`) keeps a row named to forget and again in a keep clause
unless another word of the clause names a row that word names too. Here `new` names the new card,
which `card` names as well, so the clause is read as naming only that row, as it is in `Forget my
old card 4242, keep the new card.`, which deletes the old card. The generator of 42,356 messages
has no two rows sharing a word, so its count of rows listed against the message has none of them.

## What to do

1. Write tests first: the message above keeps both cards, and `Forget my old card 4242, keep the
   new card.` still deletes the old card.
2. Add no word to a word list. Replay a shape in which the other word stops the keep only when
   each place of the row word in the clause follows it, and count the rows newly kept that the
   message asks to delete, over the generator and every string of the brain's forget tests.
3. No row may be newly listed.

## History

- 2026-11-21: filed after a replay of keep clauses naming the row to forget again
  ([R-1280](1280-a-word-naming-no-row-before-the-row-a-keep-clause-names-again-lists-it.md)).
