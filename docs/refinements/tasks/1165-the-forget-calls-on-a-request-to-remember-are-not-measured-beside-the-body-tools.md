# The forget calls on a request to remember are not measured beside the body tools

**Status:** done 2026-11-12
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

On 2026-11-12 the cortex called `forget_memories` on 14 of 20 first requests of a request to
remember over an empty pool, on a stack with no body, no tools sidecar and no subagents, so each
request listed five tools ([separation](../../readings/forget-calls-on-remember-rise.md)). Tonight's
code, the code of 2026-11-07, the llama-server build and adding `escalate_to_brain` and
`spawn_subagents` each left the rate within 4 of 20. On 2026-10-31 a stack with the Linux shell as
the body called it on 4 and 5 of 15
([listed tools](../../readings/unasked-tools-listed-on-remember.md)). Whether the body's tools and
the sidecar's tools bring the rate down is not measured, so it is not known whether a person's
own stack, which has a body, sees tonight's rate.

## What to do

1. Before any draw, add rows and a rule to the separation record: the four requests to remember
   `m1` to `m4`, first requests recorded on a stack with the Linux shell as the body, then the same
   requests with the body's tools removed, five draws each, sent to the model host directly.
2. If the body's tools bring the rate under 5 of 20, write that into
   [task 1163](1163-a-refused-forget-call-on-a-request-to-remember-costs-a-round.md), whose rows then
   run with the body attached.

## History

- 2026-11-12: filed from the separation of the rise in forget calls, whose draws could not rebuild
  the body's and the sidecar's tools.
- 2026-11-12: done. On `cortexn21`, with first requests recorded from a brain with the Linux shell
  as the body, schedules and the filesystem sidecar, the body's tool left the rate at 16 of 20,
  the same as H's five tools, and the sidecar's tools lowered it from 35 to 14 of 40 draws
  ([draws](../../readings/forget-calls-on-remember-rise.md#the-body-and-the-sidecar-the-draws-2026-11-12)).
  So task 1163's rows need no body, and they ran on that full tool list.
