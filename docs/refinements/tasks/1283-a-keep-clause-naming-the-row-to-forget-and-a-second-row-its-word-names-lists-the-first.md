# A keep clause naming the row to forget and a second row its word names lists the first

**Status:** done 2026-11-23
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

Over the rows `Remember that my card is 4111 1111 1111 4242.`, `Remember that my new card is 5500
0000 0000 4242.` and `Remember that my locker code is 4242.`, with the call text `4242`, `Forget
the card 4242, keep the card and my new card.` lists the first card, which the message asks to
keep, and so does `Forget the card 4242, keep my new card and the card.`. `_restated`
(`forget_inside.py`) keeps a row named to forget and again in a keep clause unless another word of
the clause names a row that word names too. Here `new` names the new card, which `card` names as
well, so the clause is read as naming only that row, as it is in `Forget my old card 4242, keep
the new card.`, which deletes the old card. The generator of 42,356 messages has no two rows
sharing a word, so its count of rows listed against the message has none of them.

The order of the two words in the clause does not separate these messages. In `keep my new card
and the card` each place of `card` follows `new`, as it does in `keep the new card`. Over the
Spanish rows `Recuerda que mi tarjeta es 4111 1111 1111 4242.` and `Recuerda que mi tarjeta nueva
es 5500 0000 0000 4242.`, `Olvida la tarjeta 4242, guarda la tarjeta nueva.` deletes the first
card, as it asks, and `Olvida la tarjeta 4242, guarda la tarjeta y mi tarjeta nueva.` lists it,
and in both the row word is before `nueva`. The count of the row word differs in all five: the
clause naming only the second row holds it once, and the clause naming both holds it twice.

## What to do

1. Write tests first, in English and in Spanish: each message above whose keep clause holds the
   row word twice keeps both cards, in either order, and each whose clause holds it once still
   deletes the first card.
2. Add no word to a word list. Replay a shape in which the other word stops the keep only when
   the clause holds the row word once, and count the rows newly kept that the message asks to
   delete, over every string of the brain's forget tests and over a pool with two rows sharing
   a word, which the generator lacks. `keep the new card, the card from May` holds the word
   twice and names one row, so that shape would keep the first card there.
3. `forget_inside.py` is at the limit of 300 lines, so the change adds no line or first moves a
   reader out of the file.
4. No row may be newly listed.

## History

- 2026-11-21: filed after a replay of keep clauses naming the row to forget again
  ([R-1280](1280-a-word-naming-no-row-before-the-row-a-keep-clause-names-again-lists-it.md)).
- 2026-11-23: done with the rule of
  [R-1280](1280-a-word-naming-no-row-before-the-row-a-keep-clause-names-again-lists-it.md): a
  row any reading of a keep clause names is kept, so both orders in English and the Spanish form
  keep both cards. The cost is the other direction of this task's near misses: 36 rows in 33
  messages forgetting one of two cards and keeping the other by a longer name now keep both, as
  `Forget my old card 4242, keep the new card.` ([readings](../../readings/forget-keep-any-reading.md)).
