# A forget of everything keeping a row in words no reader reads makes no forget call

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-15

Drawn on the stack brain over four stored rows
([readings](../../readings/forget-everything-unread-role.md#drawn-after-the-card-changes-2026-11-15)):
`Forget everything, my card stays.` and `Uită tot în afară de card.` made no forget call in 4 of
4 draws, and each reply said the other memories were cleared or that only the card was stored.
The first request held the card row alone: recall ranked it, and `with_forget_reach`
(`forget_reach.py`) adds the nearest rows only beside a keep clause that
`asks_to_forget_keeping` reads. Each reply ended with a true note that nothing was deleted
(`UNFORGOTTEN_CLAIM_NOTE` or `UNCALLED_FORGET_NOTE`), so the person is not misled, and the rows
asked to delete stay stored. The first note's advice, to ask again in a message of its own,
gives the same turn again. A call would not help: the card keeps every row of the English
message, and for the Romanian one a call naming `card` lists the card, since `tot` is unread
(filed with the other unread words for all).

## What to do

1. Write the rows and the pass rule into the readings before any draw: over both messages,
   count the replies that claim a delete, the notes shown and the rows the person ends up with.
2. Append a typed note that is true on every turn it reaches: when `everything`
   (`forget_permit.py`) reads the message, its unread words name a stored row and no forget call
   of the turn deleted a row, name a form the card reads, as `Forget everything but my card.`
3. Leave the first request as it is for this form while the card keeps every row under it: each
   call would return `KEPT_ALL`.

## History

- 2026-11-15: filed from the audit draws of the day's card changes.
