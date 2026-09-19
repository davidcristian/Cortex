# A fair-share policy across a batch

**Status:** open, waiting for its trigger
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-09-19
**Trigger:** the tool audit trail shows a subagent task refused by the spent turn pool while a
sibling task of the same `turn_id` made most of that turn's dispatches.

One greedy subagent can spend the turn's remaining dispatch pool before its siblings charge
anything. That degrades an answer without breaching the bound, since the starved subagent reads
the refusal and reports stopping short, so it stays deferred until it happens in practice.

## History

- 2026-08-09: A review of deferred triggers ran against the tree and none fired. Everything left
  open there needs live observation.
- 2026-09-13: Checked against the code for the first time since it was filed, and left open. The
  trigger has not fired: nothing in this tree records one subagent starving a sibling, and the only
  starvation here is the deliberate one in the runner suite's
  `test_a_run_with_no_spawning_turn_gets_its_own_allowance`, which hands a run
  `DispatchBudget(limit=0)` and asserts both of its calls are refused. The premise holds:
  `MAX_TOOL_DISPATCHES` in `brain/packages/core/src/cortex_core/tool_budget.py` is still one pool
  spent across every round of every loop a turn runs, `TurnStamp.budget` still passes that one
  handle down to whatever a call spawns, and a subagent that reaches the bound still reads
  `BUDGET_EXHAUSTED_MSG` from `dispatch.py`, which is what makes the degradation reportable rather
  than silent.
- 2026-09-19: Checked again, trigger restated, left open. "Starvation shows up in practice" was
  true or false but named nowhere to read it. It now names the audit trail, which has what the
  question needs on every line: `turn_id` and `task_id` for whose call it was, and on a refused
  call `ok=false` with `error` holding `BUDGET_EXHAUSTED_MSG` whole, the message being far under
  the formatter's 2048-character cut. Written to the file `CORTEX_TOOLS_AUDIT_FILE` names, that is
  one query per turn. Nothing in the tree records such a turn. One precision on the premise:
  `MAX_TOOL_DISPATCHES` is 32 units of price rather than 32 calls. An unpriced tool costs
  `DEFAULT_TOOL_COST` (1) and `config_tools.py` prices `spawn_subagents` at `DEFAULT_SPAWN_COST`
  (8), and an operator may price any other tool through `CORTEX_TOOLS_COSTS`, so a sibling calling
  a priced tool empties the pool in fewer calls. The runner case is still `test_runner.py:407`.
