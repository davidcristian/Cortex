# The batch cap on `spawn_subagents`

**Status:** landed 2026-07-14
**Area:** tools-mcp
**Origin:** [ADR-0010](../../adr/ADR-0010-subagents.md)

The shared pool bounded a batch's dispatches, never its
**model runs**, so one call could still ask for any number of subagents, each an admission slot,
a placement, and an inference. The pool could not close this itself, because the two count
different currencies: a tool-less subagent spends nothing from it, and
`ResourceBudgetScheduler.admit` **queues** rather than refuses (ADR-0012, by design), so an array
of fifty was never an error the cortex saw, just fifty inferences the turn sat through, two at a
time under the default CPU budget. `MAX_SPAWN_BATCH = 8` (a constant beside `MAX_TOOL_DISPATCHES`,
since how many subtasks one *call* may ask for is policy, while what the host runs *concurrently*
is the deployment fact the CPU-budget env already tunes) **refuses** an oversized batch rather
than truncating it, since dropped subtasks would hand the cortex an aggregate that reads as
complete, whereas the `is_error` result is one the model corrects by re-delegating in batches that
fit. The check runs **ahead of item parsing**, so nothing is stored and nobody is placed, and the
cap is advertised as the array's `maxItems` plus prose, so the runtime check is a backstop rather
than the first the cortex hears of it. Per call rather than a turn-wide pool: the turn-wide
addendum's "one number, not a product" argument was really about a factor that was *unbounded*,
and both factors are deliberate now (a spawn costs a quarter of the pool by default, so a turn
affords four batches, ceiling 32 model runs), while a closing turn-wide pool would end delegation for the whole
turn on the first oversized batch instead of correcting it. One property fell out rather than
being designed: a refused batch still costs its spawn price (the loop charges ahead of the
dispatch), so retry spam is bounded at four attempts. CI-gated at 100% and mutation-proven (cap,
comparison, advertisement; each reverted individually turns a distinct test red). Remaining behind
the same tool: a **`CORTEX_SUBAGENTS_MAX_BATCH` knob** if a host ever wants a different ceiling,
and a **cost-aware batch** (a cap in placements or estimated VRAM rather than in items) if roster
entries ever differ enough that eight of one is not eight of another.

## Trail

- 2026-07-14: Recorded in the ADR-0010 batch-cap addendum.
