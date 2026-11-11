# A forget sparing a row after everything but lists that row

**Status:** done 2026-11-12
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

A forget that spares a row with `but` after a word for all lists that row on the destructive card.
A unit call on 2026-11-11 with two rows, `User: My card is 4111 1111 1111 4242.` and
`User: Code 4242.`, and a call of `4242` for `Forget everything but my card.` kept only the code
row, so the card listed the card row for deletion. `_opens_keep` (`forget_unnamed.py`) opens a
keep clause on a word for except such as `except` or `sauf`, but `but` opens one only before a
negation, since `but` alone is too common a word to open one. The safe direction of the card keeps
rows. `Forget all but my card.` reads the same way.

## What to do

1. Write near misses as tests first: `Forget my card 4242, but quickly.` and
   `Forget all of my card 4242, but quickly.` still list the card row.
2. Open a keep clause on `but` only right after a word for all (`everything but`, `all but`), and
   check every keep clause form `test_forget_keep_clause.py` and `test_forget_keep_except.py`
   cover still works.
3. Check the line cap of `forget_unnamed.py`, which is at 300 lines.

## History

- 2026-11-11: filed while closing the `except` keep clause, with the unit call above
  ([readings](../../readings/forget-keep-except.md#a-word-for-except-2026-11-11)).
- 2026-11-12: done. `but` right after a word for all now opens a keep clause (`_BUT` in
  `forget_unnamed.py`), and a `but` after any other word or a clause mark opens none. A replay of
  995 recorded forget strings changed 15 cases from the 3 target strings, none keeping fewer rows;
  the live neighbouring flows drew no regression, and the `but` forms made no call, filed as task
  1150 ([readings](../../readings/forget-keep-except.md#but-after-a-word-for-all-2026-11-12)).
