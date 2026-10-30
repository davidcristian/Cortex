# A reply can say a forget request was taken care of with no call

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-10-30

`claims_forgotten` (`forget_claim.py`) reads a statement that something was forgotten, or
removed, deleted, erased, wiped or cleared from memory, and `limit_notes` then appends
`UNFORGOTTEN_CLAIM_NOTE` on a turn whose forget calls deleted nothing. In one of the 12 seeded
W03 and W04 draws that measured it
([readings](../../readings/forget-request-wordings.md#a-removal-claimed-with-no-forget-call-the-candidate-2026-10-30)),
the cortex made no call and ended "I have also taken care of your request regarding the locker
code." The row holding the code stayed, the reply names no removal, and no note was appended, so
the person can read it as done.

## What to do

1. Write rows and a rule into the readings before any draw: W03 drawn with the value stored, and
   the share of no-call replies that say a forget request was handled without naming a removal.
2. If such replies recur, consider a note on any turn that asked to forget (`asks_not_kept`) and
   ran no `forget_memories` that deleted a row, whatever the reply says, and measure it against
   the requests to remember that `asks_not_kept` must not read.

## History

- 2026-10-30: filed from the draws of the check of a removal claimed with no forget call.
