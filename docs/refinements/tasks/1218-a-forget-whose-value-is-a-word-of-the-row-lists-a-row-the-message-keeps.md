# A forget whose value is a word of the row lists a row the message keeps

**Status:** done 2026-11-21
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

Over the rows `Remember that my locker code is card.`, `Remember that my card is 4111 1111 1111
card.` and `Remember that my phone is 0721 555 card.`, with the call text `card`, `Forget the card
card, the card stays.` and `Forget card on the card, the card stays.` list all three rows, the
card among them, which the message asks to keep. With the call text `4242` and rows holding
`4242`, the same messages keep all three. `kept_again` (`forget_clauses.py`) reads only the words
past the last place a run holds the value, and here the value is the word naming the row, so
no word after it names the row to keep, while `before_value` and `beside` read `card` as a row
the message asks to forget. Of 42,356 generated messages 4 list such a row.

## What to do

1. Write tests first: both messages keep the card row.
2. Replay a shape that keeps every row when the call text holds no digit and is a word the
   message uses to name a row, and count the rows it newly keeps that the message asks to delete
   over every string literal of the brain's forget tests.

## History

- 2026-11-15: filed with the change that keeps a row a keep clause names beside another row
  ([readings](../../readings/forget-keep-except.md#the-role-of-a-row-named-after-the-value-2026-11-15)).
- 2026-11-21: done. Both messages still listed all three rows. `kept_again` now reads a call
  text that is itself a word naming a row as that row's name where it follows a word for the or
  my, so the run `the card stays` names the card to keep. Both messages keep all three rows, as
  they do for the call text `4242`, and `Forget the card card.` and `Forget the card card, only
  the card.` list them as before. Over the generator the cases listing a row the message asks to
  keep went from 18 to 14, with no row newly listed and 16 newly kept. Two of the 16 are rows the
  message asks to delete, the card of `Forget card on the card but the locker.` and of the same
  message naming the phone, which the call text `4242` keeps as well. No string of the brain's
  forget tests changed. Keeping every row for such a call text was not built: reading every later
  place of the word as a name also kept the card of `Forget the card card but the locker.`, which
  the call text `4242` lists. The replay is in
  [the readings](../../readings/forget-keep-except.md#the-role-of-a-row-named-after-the-value-2026-11-15).
  A row named to stay with no word for the or my is still listed, as in `card stays`:
  [R-1281](1281-a-forget-whose-value-is-a-word-of-the-row-lists-a-row-named-to-stay-with-no-article.md).
