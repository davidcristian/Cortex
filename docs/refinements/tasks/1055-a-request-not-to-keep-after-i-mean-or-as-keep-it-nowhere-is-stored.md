# A request not to keep after "I mean" or as "keep it nowhere" is stored

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Verified:** 2026-11-08

`asks_not_kept` in `memory_request.py` reads `don't store it` only where a request opens a clause
(`_OPENS`), so `I mean don't store it.` reads as no request, and it reads no negative object, so
`Keep it nowhere.` reads as none either. Both are stored. Beside the keep idiom, which reads as a
request to share, the message keeps nothing that asks not to keep:
`Don't keep it to yourself; I mean don't store it.` and
`Do not keep this to yourself, keep it nowhere.` both return False. The safe direction is that
the reader withholds when unsure.

## What to do

1. Write near misses first (`I mean, don't forget it`, `keep it somewhere safe`), then read a
   negation after `I mean` and `nowhere` as an object, and replay the recorded draw messages.

## History

- 2026-11-08: filed by the second audit of the night's changes, from unit probes.
