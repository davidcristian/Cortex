# A row named before the words asking to keep it is deleted

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-15

Over the rows `Remember that my locker code is 4242.`, `Remember that my card is 4111 1111 1111
4242.` and `Remember that my phone is 0721 555 4242.`, with the call text `4242`, each of these
messages deletes all three rows, the card included, which the message asks to keep: `Forget all
4242, card stays.`, `Forget all 4242, the card I still need.`, `Forget all 4242, my card
remains.` and `Forget all 4242, the card is to stay.`. Over the German rows of the same three
facts, `Vergiss alle 4242, die Karte brauche ich noch.` deletes all three. `after_value`
(`forget_clauses.py`) reads the words up to the last word naming a row and, after it, only a
negation, so no word after `card` is read. `Forget all 4242, leave the card as well.` deletes the
card too, since a run holding an adding word is read as adding a row. The card lists the row
before the person approves, but the misread deletes a row the message asks to keep, which is not
the card's safe direction.

Reading every content word after the row name as a word that may ask to keep kept the card of
`Forget every 4242, the card first.`, which asks to delete it (replayed 2026-11-15).

## What to do

1. Write tests first: each message above keeps the card; `Forget every 4242, the card first.`,
   `Forget 4242 on the card please.` and `Forget the locker 4242 but the card too.` delete the
   card.
2. Add no verb to a word list. Replay a shape that reads the words after the row name the way
   `after_value` reads the words before it, and keeps the row when a word after it is read by no
   reader. Count the rows it newly keeps that the message asks to delete.
3. Replay every string literal of the brain's forget tests through the card before and after:
   each row newly deleted must be one the message asks to delete.

## History

- 2026-11-15: filed with the change that keeps the rows a message names after the value past a
  word no reader reads
  ([readings](../../readings/forget-keep-except.md#words-after-the-value-that-no-reader-reads-2026-11-15)).
