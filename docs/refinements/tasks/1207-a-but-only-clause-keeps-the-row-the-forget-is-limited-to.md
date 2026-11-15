# A but only clause keeps the row the forget is limited to

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-15

Over the rows `Remember that my locker code is 4242.`, `Remember that my card is 4111 1111 1111
4242.` and `Remember that my phone is 0721 555 4242.`, with the call text `4242`, the messages
`Forget 4242 but only the card.` and `Forget the card 4242 but only the card.` keep all three
rows, where the message asks to delete the card. `after_but` (`forget_clauses.py`) returns the
words after `but` as words that may ask to keep a row, and no reader has a word for only. This
keeps a row, the safe direction, and the kept note shows it
([readings](../../readings/forget-keep-except.md#a-word-for-but-after-the-forget-verb-2026-11-15)).

With a word for all, `Forget all 4242 but only the card.` and `Forget every 4242 but just the
card.` keep the card and delete the locker and phone rows, which the message does not ask to
delete. That is not the card's safe direction.

## What to do

1. Write tests first: all four messages delete the card and keep the locker and the phone; `Forget
   all 4242 but the card only.` and `Forget all 4242 but not only the card.` keep the card.
2. Replay a positively matched shape that needs no new word list: the rows named after `but only`
   are the rows to delete, and every other row is kept. The two forms without a word for all may
   be declined, since their row is kept and shown; the two with one may not.
3. Replay every string literal of the brain's forget tests through the card before and after: each
   row newly deleted must be one the message asks to delete.

## History

- 2026-11-15: filed with the change that keeps the rows a word for but may ask to keep.
