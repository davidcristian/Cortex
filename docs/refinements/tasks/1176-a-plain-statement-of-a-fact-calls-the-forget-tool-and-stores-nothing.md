# A plain statement of a fact calls the forget tool and stores nothing

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-13

`My locker code at the pool is 7319.` is a store turn of the neighbouring forget draws. Tonight 3
of its 8 store turns on the `cortexn21` stack called `forget_memories`, which matched no row, and
the reply then said nothing in the message was kept in memory, so the forget turn after it had no
row to delete ([readings](../../readings/forget-group-holder-unnamed.md#neighbouring-flows-on-the-live-stack-what-was-drawn)).
All eight ran a build with the narrowed forget refusal, under which `forget_unrequested` returns
no tool for this message; at the start build `cec7c748f` it returns `forget_memories`. An earlier
night's j row drew the same store turn 4 of 4 with a stored row
([forget-keep-except.md](../../readings/forget-keep-except.md)).

## What to do

1. Separate the rise before any fix: draw the same store turn on a brain built from
   `cec7c748f` and from HEAD, with the rows and a pass rule written into the readings first.
2. If the narrowed refusal is the cause, refuse the forget tool on a statement naming no forget
   verb by its shape, without widening a word list, then replay every recorded store message.

## History

- 2026-11-13: filed from the neighbouring flow draws of the group holder keep.
