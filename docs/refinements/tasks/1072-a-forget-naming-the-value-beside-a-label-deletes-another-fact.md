# A forget naming the value beside a label deletes another fact

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-09

`unnamed` in `forget_unnamed.py` keeps a row apart only when the call's value is one the person's
message lacks. When the message names the value only to identify a fact, as in `Forget my gym
locker number, it is 5521.`, every row holding the value is listed for deletion. On 2026-11-09,
with the gym locker and shed padlock rows of
[the readings](../../readings/forget-shared-number.md#the-n1v-draws-2026-11-09) stored, 6 of 8
draws deleted the padlock row through an approved card: 4 by a first call of `5521`, 2 by a later
one. A message such as `Forget 5521 everywhere.` asks for every row, so the value in the message
cannot decide alone.

## What to do

1. Write near-miss messages as tests first (the value alone, the value with `everywhere` or `all`,
   the value beside a label, a label then the value in another sentence), and decide which name a
   fact apart. The safe direction is to keep rows.
2. Write rows and a rule into the readings, then draw the `n1v` flow 8 times on each build.

## History

- 2026-11-09: filed from the `n1v` draws, with task 1067's count of later calls.
