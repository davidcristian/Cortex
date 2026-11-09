# Keep it in mind for now beside a later save decision is stored

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Verified:** 2026-11-09

`asks_not_kept` in `memory_request.py` reads no request not to keep in `Keep it in mind for now,
I'll tell you later whether to save it.`, so the exchange is stored, while the person put off the
decision to save it. A reader not to keep withholds when unsure
([readings](../../readings/chat-only-limit-words.md#second-audit-probes-of-keep-it-in-mind-2026-11-09)).

## What to do

Write the message above and near misses (`keep it in mind for now`, `I'll tell you later what to
do`) as tests first, then read a deferred save decision beside a request to keep as a request not
to keep, and replay every recorded draw message.

## History

- 2026-11-09: filed by the second audit of the night's forget and schedule fixes, from unit probes.
