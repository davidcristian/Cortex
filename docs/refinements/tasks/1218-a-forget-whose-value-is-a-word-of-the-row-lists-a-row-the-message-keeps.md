# A forget whose value is a word of the row lists a row the message keeps

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-15

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
