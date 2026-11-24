# The result of a delete that leaves its number held suggests forgetting the number

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-24

When a `forget_memories` delete leaves other rows holding a number a deleted row held, `forgot`
(`forget_results.py`) returns a text the model reads that ends `a forget of the number itself
would remove them`. That is a destructive next step offered to the model. On the base build of
the [shared number readings](../../readings/forget-shared-number.md) the cortex then called
`forget_memories` with the number unasked in 6 of 8 draws and deleted a second fact. The refusal
of such a later call stopped the delete, and the text was left as it was. The kept branches of
the same function already say only that the value is still remembered.

What would close it: the clause replaced by the fact alone (the number is still remembered in
those rows), on draws over the rig of those readings with a rule written first, counting unasked
calls naming the number and replies claiming the number was forgotten, on the base and the
candidate. `NUMBERS_LEFT_NOTE`, which the person reads, is not part of this task. The draws of
[R-1219](1219-the-result-texts-a-model-reads-give-an-untrue-reason-for-a-row-kept-under-an-unread-role.md)
use the same stack brain with every card approved, so both can be drawn on one night.

## History

- 2026-11-24: filed while checking the kept texts of `forgot` for
  [R-1219](1219-the-result-texts-a-model-reads-give-an-untrue-reason-for-a-row-kept-under-an-unread-role.md).
