# A forget of every value limited to one row deletes the other rows

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-15

Over the rows `Remember that my locker code is 4242.`, `Remember that my card is 4111 1111 1111
4242.` and `Remember that my phone is 0721 555 4242.`, with the call text `4242`, the messages
`Forget all 4242 on the card.`, `Forget all 4242, only the card.` and `Forget all 4242 only on the
card.` delete all three rows, where the message limits the forget to the card. `quantifies`
(`forget_unnamed.py`) reads the word for all beside the value as a request for every row, so
`unnamed` keeps no row, and `after_value` (`forget_clauses.py`) reads `on`, `only` and `the` as
words naming a row to delete. Without the word for all, `Forget 4242 on the card.` deletes only
the card. The card lists the rows before the person approves, but the misread deletes two rows
the message does not ask to delete, which is not the card's safe direction. The same harm after
`but only` is
[task 1207](1207-a-but-only-clause-keeps-the-row-the-forget-is-limited-to.md).

## What to do

1. Write tests first: each message above deletes the card and keeps the locker and the phone;
   `Forget all 4242.` and `Forget all 4242, the card too.` delete all three rows, and `Forget
   every card ending 4242.` deletes only the card.
2. Add no word to a word list. Replay a shape in which a word for all asks for every row only
   when no run after the value that `after_value` reads as naming rows names some matched rows
   and not others. Count the rows it newly keeps that the message asks to delete.
3. Replay every string literal of the brain's forget tests through the card before and after:
   each row newly deleted must be one the message asks to delete.

## History

- 2026-11-15: filed from a probe of the card made with the change that keeps the rows a message
  names after the value past a word no reader reads
  ([readings](../../readings/forget-keep-except.md#words-after-the-value-that-no-reader-reads-2026-11-15)).
