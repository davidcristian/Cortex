# A row named before the value and kept in a later clause is deleted

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-15

Over the rows `Remember that my locker code is 4242.`, `Remember that my card is 4111 1111 1111
4242.` and `Remember that my phone is 0721 555 4242.`, with the call text `4242`, the message
`Forget the card 4242, card stays.` deletes the card, which its second clause asks to keep.
`_may_keep` (`forget_inside.py`) keeps every row when a run after the value names a row in a role
no reader reads, except a row the words before the value name (`before_value` in
`forget_clauses.py`), so that `Forget the card 4242, my phone is new.` still deletes the card. The
card lists the row before the person approves, but the misread deletes a row the message asks to
keep, which is not the card's safe direction.

## What to do

1. Write tests first: the message above keeps the card; `Forget the card 4242, my phone is new.`
   and `Forget the locker code 4242 and my phone number ending 4242.` delete the rows they name
   before the value.
2. Add no word to a word list. Replay a shape in which a row the words before the value name is
   kept when the same word is in a later run whose role no reader reads. Count the rows it newly
   keeps that the message asks to delete.
3. Replay every string literal of the brain's forget tests through the card before and after:
   each row newly deleted must be one the message asks to delete.

## History

- 2026-11-15: filed with the change that reads the role of a row named after the value
  ([readings](../../readings/forget-keep-except.md#the-role-of-a-row-named-after-the-value-2026-11-15)).
