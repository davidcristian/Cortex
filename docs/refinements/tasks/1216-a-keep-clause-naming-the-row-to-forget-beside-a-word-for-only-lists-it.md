# A keep clause naming the row to forget beside a word for only lists it

**Status:** done 2026-11-21
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

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
3. Replay the generator in `~/.cache/cortex-run/2026-11-15/slot7/` before and after: no
   row may be newly listed.

## History

- 2026-11-15: filed with the change that keeps a row a keep clause names beside another row
  ([readings](../../readings/forget-keep-except.md#the-role-of-a-row-named-after-the-value-2026-11-15)).
- 2026-11-21: done. Both messages still listed the card. `_restated` now reads where each other
  word of the keep clause is: a word naming no row stops the keep only before the first word
  naming the row again, as `need` of `Forget the card 4242, I don't need the card.`, and a word
  naming a row that word also names stops it anywhere, as `new` of `keep the new card`. Both
  messages and their French forms with `seulement` keep the card. Over the generator the cases
  listing a row the message asks to keep went from 135 to 18, with no row newly listed and 117
  newly kept, none a row its message asks to delete. Among the strings of the brain's forget
  tests the cost is two messages: `keep the card statement` and `keep the card and the statement`
  now keep the card. The replay is in
  [the readings](../../readings/forget-keep-except.md#the-role-of-a-row-named-after-the-value-2026-11-15).
  A word naming no row before the row word still lists it, as in `keep only the card`:
  [R-1280](1280-a-word-naming-no-row-before-the-row-a-keep-clause-names-again-lists-it.md).
