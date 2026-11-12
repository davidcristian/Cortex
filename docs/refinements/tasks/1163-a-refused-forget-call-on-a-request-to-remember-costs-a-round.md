# A refused forget call on a request to remember costs a round

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-12

`unasked_forget` (`unasked_tools.py`) refuses `forget_memories` by name on a request to remember
that only states a fact, and `_turn_tools` (`tool_loop.py`) keeps the tool in the list, so the
first request of the turn is the same as without the reader. On 2026-11-12 the `cortexn20` proxy
log held 135 first requests of such turns, and 94 of them called the tool. Each call was refused,
and the model's request after the refusal took a median 2.8 times a first request's median
([readings](../../readings/side-effect-tools-second-clause.md#a-clause-asking-to-forget-2026-11-12)).
Leaving the tool out of the list would save that round, but leaving `set_volume` and
`schedule_task` out once raised the forget calls from 1 of 30 to 13 of 30
([listed tools](../../readings/unasked-tools-listed-on-remember.md)), so a shorter list can move
other calls.

## What to do

1. Before any draw, write rows and a rule into
   [forget-refused-on-remember.md](../../readings/forget-refused-on-remember.md): the stack brain as
   baseline, and a candidate brain that also withholds the tools `unasked_forget` names, still
   refusing a call to them by name. Rows: R01 to R15 of the listed tools record over an empty pool,
   and `Remember that my gym code is 4242.` beside a stored card row, drawn on both builds in turn.
2. The candidate ships when its turns store the fact in no fewer draws, call no sidecar, schedule
   or volume tool more often than the baseline, and take a lower median time. Otherwise the tool
   stays listed and this task is declined with the rows.

## History

- 2026-11-12: filed from the replay of the store turns in the `cortexn20` proxy log.
