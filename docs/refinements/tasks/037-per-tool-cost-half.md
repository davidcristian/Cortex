# The per-tool cost half of the budget

**Status:** landed 2026-07-14
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

The budget counted *calls*, so 32 filesystem reads
and 32 `spawn_subagents` batches spent it identically. The loop now keeps a running spend and
charges each call `dispatcher.cost_of(name)` from a `ToolCostPolicy` that lives on the
dispatcher beside the gated-name set (a composition-root declaration by name, never read off
a `ToolSpec`, so a sidecar cannot price itself). Unpriced tools cost 1, so with nothing priced
the budget is the call count it was, and neither `ToolLoopContext` builder needed a new
parameter. A call that does not fit **closes** the budget rather than being stepped over, so
the refusal's "stop calling tools" stays true and the turn's spend does not depend on call
order. Only `spawn_subagents` is priced by default (`MAX_TOOL_DISPATCHES // 4`, four
delegations a turn): it is the one wired tool that fans out into a batch of model runs with no
gate in front of it, whereas `send_email` is deliberately left unpriced because the ADR-0022
confirmation is the far tighter bound on it. `CORTEX_TOOLS_COSTS__<name>` is validated to
`1..MAX_TOOL_DISPATCHES` at boot (free and unaffordable both hide rather than announce
themselves), and because a nested-dict env key replaces the whole mapping, the built-in prices
are merged *under* the user's so pricing one tool cannot silently unprice another. CI-gated
at 100% and mutation-proven (four guards, each reverted individually to red). It also moved
`MAX_TOOL_DISPATCHES` into the new `tool_budget.py` beside the prices (one currency: that
module owns how much a loop may *spend*, `tool_loop.py` how *long* it runs), which the line
cap forced by failing at 302 on `cortex_core/__init__.py`. Remaining:

## Trail

- 2026-07-14: Recorded in the ADR-0009 cost addendum.
