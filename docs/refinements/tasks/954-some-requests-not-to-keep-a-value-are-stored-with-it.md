# Some requests not to keep a value are stored with it

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-10-30

`asks_not_kept` (`memory_request.py`) reads a "don't save", "don't keep", "forget" or "not for
your memory" request. It misses other common ways to ask that a value not be kept, and the
turn's exchange is then stored with the value whenever the model makes no forget call.

Each of these returns False from `memory_withheld(caps, TaintLedger(), (), query=...)` with
memory on, so the code is stored with the exchange:

- `No need to remember this, my PIN is 5521.`
- `You don't need to save this: my PIN is 5521.`
- `Please keep this to yourself and don't write it down: my PIN is 5521.`

## What to do

1. Write these three, and the wordings in
   [forget-request-wordings.md](../../readings/forget-request-wordings.md), into the reader's
   `NOT_KEPT` table, with the `KEPT` table as the rows it must still pass.
2. Extend the reader to "no need to" and "you don't need to" before a keep verb, and to "don't
   write it down"; then draw the wordings record's rows again to see whether the model's own
   forget calls change.

## History

- 2026-10-30: filed from the closing audit of the night's memory request readers.
