# A correction of a stored value says "updated" and keeps the old row

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-10

Flow x8 of [the readings](../../readings/overlay-corrections-flows.md), every card approved: one
chat stored `Remember that my bike lock code is 4826.`; a second chat sent `My bike lock code is
4862, not 4826.` The turn called no tool, memory stored the exchange, and the reply said "I've
updated that for you. Your bike lock code is 4862." The row holding 4826 stayed, so two rows now
hold different codes and a later chat can recall either; `What is my bike lock code?` in the same
chat answered 4862 from the chat's own history. No closing note reads "updated" as a claim that
the old value was removed. R-967 is the form that asks to forget the old value outright. One draw
is not a rate.

## What to do

1. Write rows and a rule into the readings, then draw x8 and two other `X, not Y` corrections 6
   times each, counting turns that keep the old row and say it was updated or replaced, and ask in
   a new chat each time.
2. If the form repeats, weigh a brain-appended note after a typed check of the reply (an update
   claim on a turn with no forget call while a row holds the old value) against a result text the
   model reads.

## History

- 2026-11-08: filed from flow x8 in [the readings](../../readings/overlay-corrections-flows.md).
- 2026-11-10: left open. Rows and a rule were written in
  [the readings](../../readings/correction-keeps-old-value.md) before 18 draws of x8 and two other
  `X, not Y` corrections; 2 of 18 kept the seed row and said updated or replacing, under the rule's
  3, so no note was built. The same draws filed task 1112. `claims_updated`
  (`memory_claim_update.py`) reads a bare update claim and can serve this form too.
