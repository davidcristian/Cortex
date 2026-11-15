# A keep clause naming the row to forget beside another word lists it

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-15

Over the rows `Remember that my locker code is 4242.`, `Remember that my card is 4111 1111 1111
4242.` and `Remember that my phone is 0721 555 4242.`, with the call text `4242`, each of these
lists the card, which the message asks to keep: `Forget the card 4242, keep the card and the
phone.`, `Forget the card 4242 except the card and the phone.`, `Forget all 4242, the card stays
except the phone.` and `Forget all 4242 but the card except the phone.`. `_restated`
(`forget_inside.py`) keeps a row named to forget and again in a keep clause only when the clause
holds no other word naming a fact, so that `Forget the card 4242, keep the card statement.` still
deletes the card. In the first two messages the other word names another row. In the last two a
keep clause follows the words asking to keep the card with no clause mark, so those words are read
as part of the request to forget. Of 42,356 generated messages 1,248 list such a row, in each of
the five languages the card reads; every one joins a second phrase to a keep form with no clause
mark.

## What to do

1. Write tests first: the four messages above keep the card; `Forget the card 4242, keep the card
   statement.` deletes the card, and so does `Forget my old card 4242, keep the new card.` over an
   old and a new card row holding the value.
2. Add no word to a word list. Replay a shape that keeps a row the words asking to forget name
   when a keep clause of the same clause names it beside words that each name another row holding
   the value, and one that reads the words between the value and a keep clause as a run of unread
   role. Count the rows each newly keeps that the message asks to delete.
3. Replay every string literal of the brain's forget tests through the card before and after:
   each row newly deleted must be one the message asks to delete.

## History

- 2026-11-15: filed with the change that keeps a row named to forget and again to keep
  ([readings](../../readings/forget-keep-except.md#the-role-of-a-row-named-after-the-value-2026-11-15)).
