# A forget by value deletes another fact the message does not name

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-08

When the person asks to forget a fact by its name and the cortex knows the value from recall, it
passes the value itself to `forget_memories`, as the tool description says. If another fact holds
the same value, the one card lists both rows, and an approved card deletes both. On 2026-11-08,
with `Remember that my gym locker number is 5521.` and `Remember that the shed padlock code is
also 5521.` stored, `Forget my gym locker number.` made `5521` the first call in 2 of 8 draws on
the start build and 3 of 8 on the build that refuses a later value forget
([the readings](../../readings/forget-shared-number.md)). Each card listed both exchanges, both
rows were deleted, and every reply said only "I've forgotten your gym locker number." The refusal
of a later value call cannot reach this form, because here the value is the first call.

## What to do

1. Decide what a first call whose text is a value the message lacks does with rows holding none
   of the message's words: list them apart on the card and keep them unless the person's message
   names them, or keep listing them and close the reply with a note naming the second fact. A
   recall that restates the value is a row the person wants gone, so read the choice against
   [the restatement draws](../../readings/forget-value-repeats.md) before building.
2. Write rows and a rule into the readings, then draw the n1 setup 8 times on each build.

## History

- 2026-11-08: filed from the draws in [the readings](../../readings/forget-shared-number.md),
  beside the refusal of a later value forget that the same slot shipped.
