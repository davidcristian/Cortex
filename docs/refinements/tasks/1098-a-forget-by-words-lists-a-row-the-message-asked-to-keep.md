# A forget by words lists a row the message asked to keep

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-09

`unnamed` in `forget_unnamed.py` returns no row when the call's text holds no value, before it
reads the message's keep clause. A unit call on 2026-11-09 over a bike row and a shed row sharing
7319, with the text `bike lock code` and the message `Forget my bike lock code, keep the shed one.`,
listed the shed row for deletion under `Listed because they also hold 7319:`, since it holds the
value and the word `code`. The card shows the row before anything is deleted, but this is the
destructive card's unsafe direction.

## What to do

1. Write near misses as tests first: `Forget my bike lock code.` with the same text still lists
   the shed row, and `Forget my bike lock code, keep it.` names no row to keep.
2. Keep a row a clause asking to keep names whatever the text holds, then replay every recorded
   forget message through the old and new reader.

## History

- 2026-11-09: filed from a unit probe while leaving rows a keep clause names out of the count of
  numbers left (`probe1.py` in
  `/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot15/`).
