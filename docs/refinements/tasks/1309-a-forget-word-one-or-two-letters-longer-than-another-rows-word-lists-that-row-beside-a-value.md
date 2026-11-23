# A forget word one or two letters longer than another row's word lists that row beside a value

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-23

`extends` (`forget_kinds.py`) reads a forget word that names no row as a request word less its
last one or two letters, so `cart` names a row holding `car`, `plane` one holding `plan` and
`song` one holding `son`. Over a car row and a locker ending in `4242` and a phone ending in
`1234`, in unit calls through `ForgetChosenTool`, `Forget my cart 1234.` with the call text `car`
lists the car row, which the card kept before `extends`: `permitted` (`forget_permit.py`) adds
each row `forget_named` returns that holds no value of the message.

A replay of 57 word pairs in the five note languages, 37 of them no form of the row word, gives
these counts against the tree before `extends`. The cases and listings are in
`~/.cache/cortex-run/2026-11-23/a1/` (`mk.py`, `mk2.py`, `count.py`).

| cases | rows asked to keep newly listed | rows not asked for newly listed | rows asked to delete newly listed |
| --- | --- | --- | --- |
| 12,768, every row holding the message's value | 0 | 0 | 0 |
| 4,104, one other row holding the message's value | 0 | 135 | 65 |

Each of the 135, and 64 of the 65, has the call text equal to the short word itself. The 65 are
the word in another number (`Forget my cars 1234.` with `car`), which the rule is for.

## What to do

1. Write `Forget my cart 1234.` with the call text `car` as a test first, beside
   `Forget my cars 1234.` with the same call text, which lists the car row.
2. Find a reading that keeps the 135 and lists the 65, or one that keeps both and states the 65
   as its cost. Add no word list of endings.
3. Replay `mk2.py` at the old and new tree: no row newly listed that the message does not ask for.

## History

- 2026-11-23: filed from the close of
  [R-1286](1286-a-forget-naming-a-code-deletes-another-row-after-a-word-for-all-or-for-a-code-word-in-another-number.md).
