# A store failure after a forget deleted rows counts nothing

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-09

In `ForgetChosenTool.invoke`, a `MemoryStoreError` raised by the search after `delete_ids` returns
`the memory store failed during the forget` with a count of 0, so the rows already deleted get no
count note and the reply may say nothing was forgotten. `memory_forget_chosen.py` is at the line
cap, so the fix needs a split first ([readings](../../readings/forget-count-note.md#second-audit-probes-2026-11-09)).

## What to do

Split the result texts of `memory_forget_chosen.py` into their own module, then report the rows
`delete_ids` removed on the failure result too, with a fake store that fails after the delete as
the test.

## History

- 2026-11-09: filed by the second audit of the night's forget and schedule fixes, from unit probes.
