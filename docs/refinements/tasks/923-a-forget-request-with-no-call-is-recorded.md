# A forget request with no call is recorded

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-10-28

`record_exchange` (`turn_output.py`) skips a turn whose model named `forget_memories` in a call,
whatever happened to the call, through `TaintLedger.forget_asked`. Two requests to forget a named
value are still recorded with the value in the query, read from the code:

- **The model makes no call.** Before the tool's description changed, three of five draws asking
  to forget a passport number made none
  ([readings](../../readings/forget-chosen-memories.md#five-draws-a-row-2026-10-28)).
- **A forget cut from its round before a handoff.** The tool loop marks a call cut past a round's
  overflow slot, but the deep phase reads the mark from the handoff's loop tail, which never holds
  that call, so a turn that names more calls than a round takes and then hands off is recorded.

## What to do

1. Decide the no-call case: a typed check of the query, in the way `schedule_claim.py` checks a
   reply, needs rows first, since it reads language.
2. Keep the cut call's mark across the handoff: a `forget_asked` field on `HandoffRecord`, set by
   `snapshot` and read by `taint_ledger`, in place of the deep phase's read of the tail.

## History

- 2026-10-28: filed from the second audit of the forget tool.
- 2026-10-28: a call the model names now marks the turn whether it was refused for the budget
  or the round's size or written as unreadable JSON; the no-call case and a cut call before a
  handoff remain.
