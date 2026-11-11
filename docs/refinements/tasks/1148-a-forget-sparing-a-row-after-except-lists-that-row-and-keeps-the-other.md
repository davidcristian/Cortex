# A forget sparing a row after except lists that row and keeps the other

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-11

A forget whose message spares a row with `except` lists that row on the destructive card and keeps
the row the person asked to forget. A unit call on 2026-11-11 with two rows,
`User: My card is 4111 1111 1111 4242.` and `User: Code 4242.`, and a call of `4242` for
`Forget the code 4242 except the card.` showed a card deleting the card row, with the code row
under `KEPT_LINE`. `_opens_keep` (`forget_unnamed.py`) opens a keep clause only on a keep verb or
a leading negation, so `except the card` is read as naming the card row to delete, and `unnamed`
keeps the code row because `code` is a kind word. The safe direction of the card keeps rows.
`Forget 4242 but not my card.` showed no card and kept both rows, which is on the safe side but
forgets nothing.

## What to do

1. Write near misses as tests first: `Forget the code 4242.` still lists both rows, a fact
   holding `exception` or `excepted` opens no keep clause, and `Forget everything except my
   card.` keeps the card row.
2. Open a keep clause on `except` and `excluding`, and on the words for them in French, German,
   Spanish and Romanian only where they cannot also mean `minus` or `less`.
3. Check that `but not my card` deletes the code row and keeps the card row.

## History

- 2026-11-11: filed from the fourth audit of the night's forget changes, with the unit call above.
