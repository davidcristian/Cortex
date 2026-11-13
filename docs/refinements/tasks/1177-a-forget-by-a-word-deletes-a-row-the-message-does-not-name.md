# A forget by a word deletes a row the message does not name

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-13

Over `User: Remember that my gym code is 4242.` and `User: Remember that my bike lock code is
7319.`, `Forget my gym code.` with call text `code` lists and deletes both rows at HEAD. `unnamed`
(`forget_unnamed.py`) keeps only a row holding a value of the call's text, and `code` holds none,
while the keep of a row holding a value only inside a longer value beside a named row
(`_unnamed_groups` in `forget_inside.py`) reads values only
([readings](../../readings/forget-group-holder-unnamed.md)). `code` is a code word, so it names
neither row, and `gym` names only the first.

## What to do

1. Write the case as tests, with near misses: `Forget my codes.` and `Forget my gym code and my
   bike code.` with call text `code` list both rows.
2. Keep a row matched by a word call text that no word or kind of the forget part names when
   that part names another matched row (the card's safe direction), then replay the recorded
   forget strings with word call texts.

## History

- 2026-11-13: filed from the group holder keep.
