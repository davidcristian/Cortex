# A first item before a comma in a list adding rows is a remark

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-15

Over the rows `Remember that my locker code is 4242.`, `Remember that my card is 4111 1111 1111
4242.` and `Remember that my phone is 0721 555 4242.`, with the call text `4242` and a row `Remember that my
gym code is 4242.`, the message `Forget the card 4242, the phone, the locker and the gym too.`
deletes the card, the locker and the gym code and keeps the phone. `asking` (`forget_clauses.py`)
reads each clause between commas alone: `the locker and the gym too` adds rows, and `the phone`
holds no adding word, so it is a remark. This keeps a row, the safe direction, and the card shows
it as kept.

## What to do

1. Write tests first: the message above deletes all four rows; `Forget the card 4242, my phone,
   keep the locker and the gym too.` and `Forget the card 4242, the phone, I think, the gym too.`
   keep the phone.
2. Read a clause that is one item (a word for the or my, then fact words) as part of the list when
   the next clause adds rows and no keep clause stands between them.
3. Replay every string literal of the brain's forget tests through the card before and after, and
   count rows newly deleted: each must be one the message asks to delete.

## History

- 2026-11-15: filed while closing
  [task 1201](1201-a-clause-adding-two-rows-to-a-forget-is-a-remark.md).
