# A word for all in a clause holding a keep verb keeps a last group of another kind

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-15

Over the rows `Remember that my locker code is 4242.`, `Remember that my card is 4111 1111 1111
4242.` and `Remember that my phone is 0721 555 4242.`, with the call text `4242`, the message
`Forget every 4242 but keep the card.` lists only the locker row and keeps the phone row, while
`Forget every 4242, keep the card.` and `Forget every 4242 except the card.` list the locker and
phone rows. `quantifies` (`forget_unnamed.py`) reads no clause that holds a keep verb, so a word
for all before `but keep` in the same clause is not read. A row whose kind the table of
`forget_kinds.py` does not name is also kept by each of the three messages: a badge `9000 4242`,
or `Merke dir, mein Handy ist 0721 555 4242.`. Both keep a row, the safe direction, and the kept
note shows it.

## What to do

1. Write tests first: the first message lists the locker and phone rows and keeps the card; `Keep
   every 4242.` and `Forget 4242 but keep every card.` list nothing more than today.
2. Read a word for all in the words of a clause before its keep clause. `quantifies` has three
   other callers, so replay each of them.
3. Leave a row of no kind of the table kept unless a replay shows a shape that never deletes a row
   the keep clause names in another language.

## History

- 2026-11-15: filed while closing
  [task 1183](1183-a-forget-of-every-value-except-one-kind-keeps-a-row-of-another-kind.md).
