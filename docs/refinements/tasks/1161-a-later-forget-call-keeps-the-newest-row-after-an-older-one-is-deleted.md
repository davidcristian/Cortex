# A later forget call keeps the newest row after an older one is deleted

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-12

A forget call of a turn that already deleted a row does not apply the newest row exception, since
the earlier delete may have removed the newest row, and the turn's ledger (`_deleted_rows` in
`memory_forget_chosen.py`) keeps only row texts, with no time or chat. So when the first call
deletes an older row, a later call keeps the newest row the message asked for. Over `User:
Remember that my gym code is 4242.` stored before `User: Remember that my card is 4111 1111 1111
4242.` in the calling chat, `Forget what I just told you.` with a first call `gym code` and a
second call `4242` deletes the gym code and keeps the card, which the inside note names
([readings](../../readings/forget-keep-plain-replay.md#two-calls-and-every-row)).

## What to do

1. Keep the time and chat of each deleted row in the turn's ledger, and apply the exception on a
   later call when no deleted row of the calling chat is newer than the newest match.
2. Write the case above and its near miss as tests first (the gym code stored last: the second
   call keeps the card), then replay the strings of the readings through the old and new code.

## History

- 2026-11-12: filed from the fix that turns the exception off after a delete in the turn.
