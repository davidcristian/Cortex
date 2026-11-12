# A refused forget call on a request to remember costs a round

**Status:** declined 2026-11-13
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

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

The 94 of 135 belong to the `cortexn20` stack, whose requests to remember hold no recall block
and list five tools: its start build and the tool specs of 2026-11-07 call on 14 and 18 of 20
draws, and a recalled row holding the fact lowers it to 2 of 10
([separation](../../readings/forget-calls-on-remember-rise.md)). The rows below run on that stack.

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
- 2026-11-13: declined. A candidate that also left out the tools `unasked_forget` names stored the
  fact as often and had a lower median turn time, but called a sidecar tool on 2 of 18 draws where
  the baseline called none, so the tool stays listed
  ([draws](../../readings/forget-refused-on-remember.md#withholding-the-refused-tool-the-draws-2026-11-13)).
  The rows ran on the full tool list, since task 1165 found the body's tool does not move the rate.
