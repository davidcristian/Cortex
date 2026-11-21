# A forget whose value is a word of the row lists a row named to stay with no article

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-21

Over the rows `Remember that my locker code is card.`, `Remember that my card is 4111 1111 1111
card.` and `Remember that my phone is 0721 555 card.`, with the call text `card`, `Forget the card
card, card stays.` and `Forget the card card, that card stays.` list all three rows, the card
among them, which the message asks to keep. With the call text `4242` and rows holding `4242`, the
same messages keep all three. `kept_again` (`forget_clauses.py`) reads only the words past the
last place a run holds the value, and reads a value that is itself a word naming a row as that
row's name only after a word for the or my (`WHOSE`). Reading every later place of the word as a
name was replayed on 2026-11-21: it keeps the card of `Forget the card card but the locker.`,
which the message asks to delete and the call text `4242` lists, in 2 of 42,356 generated
messages. The generator writes each row with its article, so it holds neither message above.

## What to do

1. Write tests first: both messages keep the card row, and `Forget the card card but the locker.`
   still lists the card.
2. Replay a shape that reads the value as a row name in every run except the one that follows
   the value's first place, and count the rows it newly keeps that the message asks to delete,
   over the generator and every string of the brain's forget tests.

## History

- 2026-11-21: filed with the change that reads such a value as a row name after a word for the
  or my
  ([R-1218](1218-a-forget-whose-value-is-a-word-of-the-row-lists-a-row-the-message-keeps.md)).
