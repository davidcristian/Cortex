# The unkept note shows on a message with nothing to keep

**Status:** open, waiting for its trigger
**Area:** memory
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Trigger:** a person says the note confused them, or a recorded draw or shell flow holds a message of
this form outside the row that found it.
**Verified:** 2026-10-31

`asks_kept` reads `Remember to read notes.txt and tell me what it says.`, a to-do for this turn, as a
request to remember. The turn reads the file, stays out of memory, and ends with `UNKEPT_CLAIM_NOTE`
([draws](../../readings/claim-reader-replays.md#the-note-on-every-withheld-request-to-remember-the-draws-2026-10-31)).
The note is true, and its second sentence asks only for what the person wants remembered, so the cost is
one line they did not need.

## What to do

Write near misses first. `Remember to buy milk` is stored and must stay stored, and
`Note that my plan is in notes.txt. What does it say?` holds a fact the note is right about. A reader
that takes the to-do out reads the verb after "remember to" and whether a tool answers it this turn, and
replays every recorded message.

## History

- 2026-10-31: filed from the rows of the note on every withheld request to remember.
