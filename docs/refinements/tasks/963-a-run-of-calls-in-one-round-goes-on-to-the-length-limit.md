# A run of calls in one round goes on to the length limit

**Status:** open, actionable
**Area:** tools
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-10-31

A round can hold a run of calls the model does not stop writing. In one draw of
`Please remember this: I work as a nurse.` the cortex wrote its reply and then `set_volume` calls
with no arguments until the generation hit its length limit
([readings](../../readings/unasked-tools-listed-on-remember.md#the-draws-2026-10-31)). The turn took
about 10 times the row's median, nothing was shown during the wait, and the reply ended in the note
that it stopped at the machine's length limit. `plan_round` (`tool_round.py`) keeps
`MAX_CALLS_PER_ROUND` calls and one more, but `_round_pieces` (`tool_loop.py`) goes on reading the
stream until it ends, so the cap bounds the context and not the wait.

## What to do

1. Stop reading a round's stream once it holds one call past `MAX_CALLS_PER_ROUND`, closing the
   backend stream, and check that the reply's stop note then does not say the length limit was hit.
2. A scripted backend that writes calls without end is the unit test. The draw is rare, 1 of 27
   draws of a build listing that tool, so a row of model draws cannot check the fix in one run.

## History

- 2026-10-31: filed from the rows of
  [R-961](961-a-request-to-remember-a-stored-fact-can-show-a-forget-card.md).
