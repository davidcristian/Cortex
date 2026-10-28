# A forget request with no call is recorded

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-10-28

`record_exchange` (`turn_output.py`) skips a turn whose model named `forget_memories` in a call,
whatever happened to the call, through `TaintLedger.forget_asked`, which the handoff record keeps
for the deep phase. A request to forget a named value is still recorded with the value in the
query when the model makes no call at all: before the tool's description changed, three of five
draws asking to forget a passport number made none
([readings](../../readings/forget-chosen-memories.md#five-draws-a-row-2026-10-28)).

## What to do

1. Decide the no-call case: a typed check of the query, in the way `schedule_claim.py` checks a
   reply, needs rows first, since it reads language.

## History

- 2026-10-28: filed from the second audit of the forget tool.
- 2026-10-28: a call the model names now marks the turn whether it was refused for the budget
  or the round's size, cut from its round or written as unreadable JSON, and the mark survives a
  handoff; the no-call case remains.
