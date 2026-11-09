# A forget naming no word deletes another chat's fact

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-09

`unnamed` in `forget_unnamed.py` returns no row to keep when the message has no word left after
`_COMMON`, before `_just_said` is read. With the calling chat's bike row and another chat's shed
row both holding 7319 and the call text 7319, `Actually forget it` keeps the shed row, while
`Forget that.` and `Forget it, please.` keep nothing, so the card lists the other chat's fact
([readings](../../readings/forget-what-was-just-said.md#audit-probes-2026-11-09)).

## What to do

1. When the message holds no value and no word, keep every row but the newest the calling chat
   stored, as the `Actually forget it` form does; keep the current reading when the chat stored
   none.
2. Test both forms with two rows of the calling chat and one of another chat.

## History

- 2026-11-09: filed from the audit probes of the forget of what was just said.
