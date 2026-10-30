# A request to note a value is not read as a request to remember

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-10-30

`asks_kept` (`memory_request.py`) reads "note" only as "note that", so each of these returns
False:

- `Note my code 7319.`
- `Note down my locker number 42.`
- `Note my code 7319 and don't store it.`

On the first two, a `forget_memories` call that matched nothing makes `memory_withheld` store
nothing of the turn, so the value the person asked to keep is lost, as it was for "never forget"
before that opener was read. `unasked_tools` also leaves every tool in place on them. The third
is still read as a request not to keep, so it is withheld as it should be.

Adding a bare "note" to `_REMEMBER` is not enough: "Note: I'm off tomorrow, cancel my meeting"
would then be a request to remember, and `unasked_tools` would withhold the schedule tool from it.

## What to do

1. Add the three messages above to the `REMEMBER` and `NOT_KEPT` tables in
   `test_memory_claim.py`, and the "Note:" instruction above to the rows `unasked_tools` must
   leave alone.
2. Read "note" as a request to remember only before a value it names ("my", "this", "down",
   "the"), and run every message drawn in the readings through the old and the new reader.

## History

- 2026-10-30: filed from the second audit of the night's request reader fixes; read from the
  reader, not from a draw.
