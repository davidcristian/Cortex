# The per-tool cost half of the budget

**Status:** done 2026-07-14
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

The budget counted calls, so 32 filesystem reads and 32 `spawn_subagents` batches spent it
identically. The loop now keeps a running total and charges each call `dispatcher.cost_of(name)`
from a `ToolCostPolicy` that lives on the dispatcher beside the set of names needing confirmation.
It is declared at the composition root by name and never read off a `ToolSpec`, so a sidecar
cannot price itself. Unpriced tools cost 1, so with nothing priced the budget is the call count it
was, and neither `ToolLoopContext` builder needed a new parameter. A call that does not fit closes
the budget rather than being stepped over, so the refusal's "stop calling tools" stays true and
the turn's total does not depend on call order.

Only `spawn_subagents` is priced by default, at `MAX_TOOL_DISPATCHES // 4`, four delegations a
turn: it is the one wired tool that fans out into a batch of model runs with nothing asking the
user first, whereas `send_email` is deliberately left unpriced because its confirmation is a much
tighter bound.

`CORTEX_TOOLS_COSTS__<name>` is validated to `1..MAX_TOOL_DISPATCHES` at boot, since a free tool
and an unaffordable one both change what the budget does without reporting it, and because a
nested-dict environment key replaces the whole mapping, the built-in prices are merged under the
user's so pricing one tool cannot unprice another. Covered at 100%, with four guards each reverted
individually to a failing test.

It also moved `MAX_TOOL_DISPATCHES` into the new `tool_budget.py` beside the prices, one concern
per module: that module owns how much a loop may spend, `tool_loop.py` how long it runs. The line
cap forced that by failing at 302 on `cortex_core/__init__.py`.

## History

- 2026-07-14: Recorded in ADR-0009 decision 11.
