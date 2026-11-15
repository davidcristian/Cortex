# A keep clause naming the row to forget beside a word for only lists it

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-15

Over the rows `Remember that my locker code is 4242.`, `Remember that my card is 4111 1111 1111
4242.` and `Remember that my phone is 0721 555 4242.`, with the call text `4242`, `Forget the card
4242, keep the card only on the phone.` and `Forget the card 4242 except the card only on the
card.` list the card, which the message asks to keep. `_restated` (`forget_inside.py`) keeps a row
named to forget and again in a keep clause only when every other word of the clause names a row
the first word does not. `only` names no row, so the clause reads as `keep the card statement`,
which names another fact and deletes the card. The French `seulement` reads the same way. Of
42,356 generated messages 96 list such a row, 48 in English and 48 in French; German, Spanish and
Romanian list none, since `nur`, `solo` and `doar` are function words of their language.

## What to do

1. Write tests first: the two messages above keep the card, and `Forget the card 4242, keep the
   card statement.` still deletes it.
2. Add no word to a word list. Replay a shape that keeps the row when the other word of the keep
   clause names no row and stands after the word naming the row to keep, and count the rows it
   newly keeps that the message asks to delete; `keep the card statement` is one of them, so
   decide on that count whether a row named beside a word naming no row is kept.
3. Replay the generator in `/home/david/.cache/cortex-run/2026-11-15/slot7/` before and after: no
   row may be newly listed.

## History

- 2026-11-15: filed with the change that keeps a row a keep clause names beside another row
  ([readings](../../readings/forget-keep-except.md#the-role-of-a-row-named-after-the-value-2026-11-15)).
