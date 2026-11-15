# A phrase for except that no reader holds deletes the row it names

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-15

Over the rows `Remember that my locker code is 4242.`, `Remember that my card is 4111 1111 1111
4242.` and `Remember that my phone is 0721 555 4242.`, with the call text `4242`, each of these
messages deletes all three rows, the card included, which the message asks to keep: `Forget all
4242 apart from the card.`, the same with `other than`, `besides`, `save`, `aside from` and `with
the exception of`, `Forget all 4242, leave the card.` and `Forget all 4242, I still need the
card.`. `Forget 4242 apart from the card.` deletes only the card. Over the German and French rows
of the same three facts, `Vergiss alle 4242 bis auf die Karte.` and `Oublie tous les 4242 à part
la carte.` delete all three. None of these phrases is a word of `EXCEPT`, `KEEP` or `_CONTRAST`
(`forget_clauses.py`), so no keep clause opens, `card` names a row to delete and `quantifies`
asks for every row. The card lists the row before the person approves, but the misread deletes a
row the message asks to keep, which is not the card's safe direction.

## What to do

1. Write tests first: each message above keeps the card; `Forget all 4242 on the card.`, `Forget
   all 4242, the card too.` and `Forget every card ending 4242.` delete the card.
2. Add no phrase to a word list. Replay a shape that keeps the rows the words after the value
   name when a word for all asks for every row and those words name some matched rows and not
   others, since the words alone do not say whether they limit the forget or make an exception.
   Count the rows it newly keeps that the message asks to delete.
3. Replay every string literal of the brain's forget tests through the card before and after:
   each row newly deleted must be one the message asks to delete.

## History

- 2026-11-15: filed from a probe of the card made with the change that keeps the rows a word for
  but may ask to keep
  ([readings](../../readings/forget-keep-except.md#a-word-for-but-after-the-forget-verb-2026-11-15)).
