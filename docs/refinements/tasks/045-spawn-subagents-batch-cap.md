# The batch cap on `spawn_subagents`

**Status:** done 2026-07-14
**Area:** tools-mcp
**Origin:** [ADR-0010](../../adr/ADR-0010-subagents.md)

The shared dispatch pool bounded a batch's tool calls, never its model runs, so one call could ask
for any number of subagents, each an admission slot, a placement and an inference. The pool could
not close this, because the two count different things: a subagent that calls no tools spends
nothing from it, and `ResourceBudgetScheduler.admit` queues rather than refuses, by design, so an
array of fifty was never an error the cortex saw, just fifty inferences the turn sat through, two
at a time under the default CPU budget.

`MAX_SPAWN_BATCH = 8` is a constant beside `MAX_TOOL_DISPATCHES`, since how many subtasks one
call may ask for is policy while what the host runs at once is a deployment fact the CPU-budget
environment already tunes. It refuses an oversized batch rather than truncating it, since dropped
subtasks would hand the cortex an aggregate that looks complete, whereas the `is_error` result is
one the model corrects by re-delegating in batches that fit. The check runs ahead of parsing the
items, so nothing is stored and nobody is placed, and the cap is advertised as the array's
`maxItems` plus prose, so the runtime check is a second line of defence rather than the first the
cortex hears of it.

Per call rather than a turn-wide pool. The dispatch budget's "one number, not a product" argument
was about a factor that was unbounded, and both factors are deliberate now: a spawn costs a
quarter of the pool by default, so a turn affords four batches, a ceiling of 32 model runs. A
closing turn-wide pool would end delegation for the whole turn on the first oversized batch
instead of correcting it. One property fell out rather than being designed: a refused batch still
costs its spawn price, because the loop charges before the dispatch, so retry spam is bounded at
four attempts. Covered at 100%, with the cap, the comparison and the advertisement each reverted
individually to a distinct failing test.

Two things were left behind it: [R-046](046-a-cortex-subagents-max-batch-setting.md), a
`CORTEX_SUBAGENTS_MAX_BATCH` setting if a host ever wants a different ceiling, and
[R-047](047-cost-aware-batch-cap.md), a cap in placements or estimated VRAM rather than in items,
if roster entries ever differ enough that eight of one is not eight of another.

## History

- 2026-07-14: Added as ADR-0010 decision 9.
