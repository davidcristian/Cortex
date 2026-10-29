# A forget request with no call is recorded

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-10-29

`memory_withheld` (`memory_claim.py`), the check `record_exchange` and the reply note share, holds
for a turn whose model named `forget_memories` in a call, whatever happened to the call, through
`TaintLedger.forget_asked`, which the handoff record keeps for the deep phase. A request to forget a
named value is still recorded with the value in the query when the model makes no call at all:
before the tool's description changed, three of five draws asking to forget a passport number made
none ([readings](../../readings/forget-chosen-memories.md#five-draws-a-row-2026-10-28)).

## What to do

1. Find a wording of a forget request that makes no call. None has since the description
   changed ([readings](../../readings/forget-chosen-memories.md#ten-wordings-of-a-forget-request-2026-10-29)).
2. Then decide the no-call case: a typed check of the query, in the way `schedule_claim.py` checks
   a reply, would be one more input to `memory_withheld`. It reads language, so it needs rows
   first, and it widens the skip, so its rows include requests to remember.

## History

- 2026-10-28: filed from the second audit of the forget tool.
- 2026-10-28: a call the model names now marks the turn whether it was refused for the budget
  or the round's size, cut from its round or written as unreadable JSON, and the mark survives a
  handoff; the no-call case remains.
- 2026-10-29: 30 draws of ten wordings of a forget request naming a value, and 70 forget requests
  drawn earlier that night, all called `forget_memories`, so the no-call case has no row yet. Left
  open.
