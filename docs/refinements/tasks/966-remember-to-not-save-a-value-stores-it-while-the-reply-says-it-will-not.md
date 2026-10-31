# Remember to not save a value stores it while the reply says it will not

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-10-31

`Remember to not save my locker code 7319.` left a `memories` row holding `7319` in all 4 draws, and
every reply said the code would not be saved ([rows](../../readings/forget-refused-on-remember.md#the-draws-2026-10-31), row M04, on both
builds). `asks_not_kept` (`memory_request.py`) reads "remember not to save" and not "remember to not
save". `Remember that you should forget my locker code.` is the same gap: a draw with no call stored
its exchange, with `7319` in the query.

## What to do

1. Write near-miss tests first ("Remember to not call him after 9." and other rules to keep), then widen
   `_NOT_TO_KEEP` and `_FORGET`, and replay every recorded message through the old and new reader.

## History

- 2026-10-31: filed from the rows of the check of refusing a forget call.
