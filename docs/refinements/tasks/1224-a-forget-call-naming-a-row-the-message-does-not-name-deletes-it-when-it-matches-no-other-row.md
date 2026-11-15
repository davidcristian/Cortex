# A forget call naming a row the message does not name deletes it when it matches no other row

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-15

On 2026-11-15 unit calls through `ForgetChosenTool` over an in-memory store listed a row the
message does not ask to delete. `Forget my gym code.` over a card row and a gym code row, with the
call text `card`, listed the card row and deleted it. The same message over a locker code, a card
and a phone, with the call text `phone`, deleted the phone row. `Forget all codes but my card.`
over those three rows, with the call text `phone`, deleted the phone row too, since `but` after
`codes` opens no keep clause. `_unnamed_groups` (`forget_inside.py`) keeps a match of a call text
holding no digit only when a word of the message names another row the call matched, and each of
these calls matched one row. The card shows the row before anything is deleted.

## What to do

1. Write the near misses as tests first: `Forget what I just told you.` and a message naming no
   stored row at all must still list the row the call names.
2. Read the rows the message names from the store, as `keep_named` (`forget_keep_named.py`) does
   for a keep clause, so a match no word of the message names is kept when the message names
   another stored row.
3. Replay every recorded card case through the old and the new reader: each newly kept row must be
   one the message does not ask for.

## History

- 2026-11-15: filed from the near misses written for a call naming a row beside a forget of
  everything but one fact
  ([readings](../../readings/forget-everything-but-call.md#the-card-reading-2026-11-15)).
