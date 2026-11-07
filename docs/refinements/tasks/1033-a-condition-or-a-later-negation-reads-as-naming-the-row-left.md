# A condition or a later negation reads as naming the row left

**Status:** open, actionable
**Area:** cross-cutting
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-07

`names_still_held` in `numbers_left_claim.py` reads a reply as naming the row that still holds a
forgotten number when a sentence asking nothing has `still` before a verb such as `appears in`,
`mentions` or `stored`, and no English negation comes before it in its clause. It does not read a
condition or a negation after the verb. A reply that only offers to forget more, or says nothing
holds the number, is then read as naming the row, so `NUMBERS_LEFT_NOTE` is left out while rows
still hold the number. This is the direction that matters: the note is missing.

Reproduction, unit level (`SCRATCH/slot22/probe.py`), `names_still_held(reply)` is `True` and
`numbers_left_claim(reply, left=True)` is `False` for each:

- "I've forgotten your door code. If it still appears in another chat, tell me."
- "I've forgotten your door code. Should it still appear in a later chat, ask me again."
- "I've forgotten your door code; it still appears in no other memory."
- "I've forgotten your door code. If anything is still stored, tell me."

The first three use the verbs added to the reader tonight; the fourth is older. "The number no
longer appears in any memory" and "The number still appears nowhere" read correctly as not naming
the row.

## What to do

1. Write the four replies above as near misses first, beside the current `STILL_HELD` cases.
2. Read a sentence as naming the row only when no `if`, `should`, `whether` or `in case` opens
   its clause and no `no`, `none` or `nothing` follows the verb in the clause, so the reader fails
   toward adding the note. Replay every recorded forget reply through the old and new reader.

## History

- 2026-11-07: filed from the fourth audit of the night's changes, reproduced at unit level.
