# Some requests to forget or not to keep are not read

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-10-30

`asks_not_kept` (`memory_request.py`) returns False for each of these, so a turn that makes no
`forget_memories` call stores the exchange with the value in its query:

- `Erase the PIN 5521 I gave you.`
- `Stop remembering that my sister's name is Ana.`
- `I shouldn't have told you my card number 4242 4242 4242 4242. Please get rid of it.`
- `Unlearn my phone number 0612345678.`
- `Never mind my locker code 7319, drop it.`
- `Please remember not to store my card number.`

The first five are wordings of
[forget-request-wordings.md](../../readings/forget-request-wordings.md#ten-wordings-of-a-forget-request-2026-10-29),
and each called the tool in 3 of 3 draws, so no draw has shown the miss storing a value. The
last is worse: `asks_kept` reads it as a request to remember, so even a forget call that matched
nothing lets the turn be recorded.

## What to do

1. Add the six messages to the reader's `NOT_KEPT` table with the `KEPT` and `RULES` tables as
   the rows it must still pass.
2. Extend the reader to these forms within the rule
   [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md) decision 5 states, and run every
   message drawn in the readings through the old and the new reader to list what changes.

## History

- 2026-10-30: filed while the reader's rule for a clause after a request to remember was
  written; the six misses were read from the reader, not from a draw.
