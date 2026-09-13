# A fair-share policy across a batch

**Status:** open, fix when it bites
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-09-13
**Trigger:** Starvation shows up in practice.

One greedy subagent can spend the turn's remaining pool
before its siblings charge anything. Starvation degrades an answer without breaching the bound
(the starved subagent reads the refusal and reports stopping short), so it stays deferred until
it shows up in practice.

## Trail

- 2026-08-09: A trigger sweep of the fix-when-it-bites bucket ran against the tree and fired
  nothing. Everything left open in that bucket is live-observation shaped, its trigger being a
  deployment doing something rather than a file saying something.
- 2026-09-13: re-derived against the code for the first time since it was filed, and left open.
  The trigger has not fired: nothing in this tree records one subagent starving a sibling, and the
  only starvation here is the deliberate one in the runner suite's
  `test_a_run_with_no_spawning_turn_gets_its_own_allowance`, which hands a run
  `DispatchBudget(limit=0)` and asserts both of its calls are refused. The premise holds
  unchanged. `MAX_TOOL_DISPATCHES` in `brain/packages/core/src/cortex_core/tool_budget.py` is
  still one pool of 32 spent across every round of every loop a turn runs, `TurnStamp.budget` still
  carries that one handle down to whatever a call spawns, and a subagent that reaches the bound
  still reads `BUDGET_EXHAUSTED_MSG` from `dispatch.py`, which is what makes the degradation
  reportable rather than silent.
