# No record of it remains since you never told me gets no note

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-09

`_HELD` in `forget_unfound_claim.py` applies to the singular `no record of` as well as the plural,
so `says_not_stored` is now false for `No record of it remains, since you never told me that.`,
`There is no record of it left, because you never gave it to me.` and `No record of it exists
because you never mentioned it.`, which the reader before the plural change read as a never stored
claim. The note after a delete is then not shown; a note's safe direction is to show
([readings](../../readings/forget-later-call-other-words.md#audit-replay-of-the-plural-reader-2026-11-09)).

## What to do

1. Write the three replies above as tests, beside `No other records of it remain.` as the near
   miss that must stay unread.
2. Read a sentence that also says the person never told, gave or mentioned it as a claim whatever
   follows `no record of`, and replay the recorded replies through the old and new reader.

## History

- 2026-11-09: filed from the audit replay of the plural reader.
