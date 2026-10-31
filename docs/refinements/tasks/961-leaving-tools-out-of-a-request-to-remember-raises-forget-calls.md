# Leaving tools out of a request to remember raises forget calls

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-10-31

On a request to remember, the cortex called `forget_memories` in 13 of 30 draws with `set_volume`
and `schedule_task` left out of its tool list, against 1 of 30 with them in it, on two builds drawn
in turn ([readings](../../readings/side-effect-tools-on-remember.md#the-forget-calls-on-a-request-to-remember-separated-pair-the-draws-2026-10-31)).
With an empty pool every call matched nothing, showed no card and kept the fact, and the reply said
the fact was noted. A pool holding the same text makes `card` (`memory_forget_chosen.py`) list
stored memories, so a request to remember a fact already stored could show a forget card, and no
row has drawn that since the change.

## What to do

1. Write rows and a rule into the readings before any draw. The rows need a seeded pool holding
   the fact, since only that case can show a card, and the rule must say what a Deny costs: a
   declined forget still keeps the turn out of memory.
2. Consider leaving both tools in the list and refusing a call by name. The request then matches
   the one that drew 1 of 30. The side-effect rule of
   [R-901](901-a-request-to-remember-a-fact-can-set-the-volume.md) must still hold.
3. Change no shipped behaviour on the counts above alone.

## History

- 2026-10-31: filed from the separated pair of
  [R-952](952-withheld-unasked-tools-may-raise-forget-calls-on-a-remember-request.md).
