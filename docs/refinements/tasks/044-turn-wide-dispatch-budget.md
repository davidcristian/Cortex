# The turn-wide dispatch budget

**Status:** done 2026-07-14
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

The per-loop budget and its prices claimed that one number answers how many external calls one
turn can make, and delegation made that false: `spent` was a local in `stream_tool_loop` and the
runner builds a fresh `ToolLoopContext` per task, so every subagent started at zero. The entry's
own "can exceed 32 in aggregate" understated it, because `spawn_subagents` takes an unbounded
`instructions` array: four batches, all that the `MAX_TOOL_DISPATCHES // 4` price allows, of fifty
subagents each is 6400 dispatches for a spend of 32. The price bought bounded batches and
unbounded calls.

The counter is now a `DispatchBudget` object in `tool_budget.py` (`charge(cost) -> bool`, which
also moves "a call that does not fit closes the budget" out of the loop and into the budget), and
it reaches spawned work on the `TurnStamp`, the channel the loop already stamps and
`spawn_subagents` already reads for taint, so no `dispatch()` keyword and no second field on
`ToolCall` were added. That is the stamp's first field that is not provenance, a deliberate
widening to what the dispatching turn hands the work this call spawns, and the handle is excluded
from the stamp's equality (`compare=False`) since a shared resource is not part of a value.

One pool, first come first served, rather than a share per subagent: dividing the remainder would
have to estimate how many of a batch will call tools at all, and it makes the answer a function of
fan-out again, which is the arithmetic being removed. Closure is turn-wide too, so
`BUDGET_EXHAUSTED_MSG`'s "this turn has reached its limit" is literally true.

The spawn price stays, because the two bounds count different things: the pool counts dispatches,
and a subagent that calls no tools spends nothing from it while still costing an admission slot, a
placement and a model run. A root caller with no pool, such as the scheduler firing, still gets
its own, unchanged. Covered at 100% with six guards each reverted individually to a failing test.

## History

- 2026-07-14: Recorded in ADR-0009 decision 11.
