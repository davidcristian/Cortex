# A forget request whose call never ran is recorded

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-10-28

`record_exchange` (`turn_output.py`) skips a turn only when a `forget_memories` run is in its runs,
and a run exists only for a call that was dispatched with a spec. Three requests to forget a named
value are recorded with the value in the query, read from the code:

- The model makes no call. Before the tool's description changed, three of five draws asking to
  forget a passport number made none ([readings](../../readings/forget-chosen-memories.md#five-draws-a-row-2026-10-28)).
- The call is refused before it runs: `run_round` (`dispatch_round.py`) yields no `StepOutcome`
  for a call refused for the turn's budget or the round's size, so no run is noted.
- The model writes the call's arguments as unreadable JSON: `MalformedToolCallError` ends the
  round before any call is dispatched, and the engine still records the exchange.

## What to do

1. Mark the turn when the model names `forget_memories` in a call, whatever happens to it: set a
   flag on the turn's `TaintLedger` in `run_round` before the refusal check, and read it in
   `record_exchange`, with a test per refusal kind.
2. Decide the no-call case separately: a typed check of the query, in the way `schedule_claim.py`
   checks a reply, needs rows first, since it reads language.
3. For an unreadable call, see task 924, which keeps its text out of the log.

## History

- 2026-10-28: filed from the second audit of the forget tool.
