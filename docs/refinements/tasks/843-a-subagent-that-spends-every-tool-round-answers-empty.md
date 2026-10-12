# A subagent that spends every tool round answers empty

**Status:** open, actionable
**Area:** subagents
**Origin:** [ADR-0010](../../adr/ADR-0010-subagents.md)
**Verified:** 2026-10-12

A subagent with tools runs the same `stream_tool_loop` as a turn. When its eighth round still ends
in calls, the loop dispatches them and stops, and `SubagentAttempt` passes whatever text it has to
`settle_reply`, which returns it as an answer: an unconstrained run that only called tools comes
back as `SubagentResult(ok=True, output="")`. The cortex then reads an empty success where the
subtask was never answered.

The loop already reports the limit: it calls `observe_round_limit()` on the attempt's
`StopLedger`, and `out_of_rounds` reads it, as the turn's `ROUNDS_SPENT_NOTE` does
([ADR-0009](../../adr/ADR-0009-tools-mcp.md) decision 3).

## What to do

Decide what an attempt that ran out of rounds returns, for example `AttemptFailure.TRUNCATED` with
a detail naming the round limit and telling the cortex to treat the subtask as unanswered, as
`GENERATION_CAP_MSG` does for a token limit. Decide whether the CPU re-run applies (it should not:
the same model would spend the same rounds). Test it with a backend that emits a call every round.

## History

- 2026-10-12: filed when a turn that spends every tool round was given its note; the subagent path
  shares the loop and the ledger but not the note.
