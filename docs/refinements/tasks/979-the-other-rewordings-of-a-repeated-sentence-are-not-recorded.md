# The other rewordings of a repeated sentence are not recorded

**Status:** open, actionable
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-11-05

In 6 of the 20 A4 draws of
[reply-repeat-across-a-tool-call.md](../../readings/reply-repeat-across-a-tool-call.md#more-than-one-repeated-sentence-result-2026-10-31),
the second round restated the first round's second sentence in other words. The run log was lost,
and the readings quote one of the 6, which `OpeningHold` now drops: it differs from the earlier
sentence only by a closing `as you requested`. Whether the other 5 differ in the same way is not
known, so a reply may still say the same thing twice.

## What to do

1. Record a second-round request of a W04 draw with the recording proxy, set its first round and
   result to A4's, and write into the readings, before any draw, a row of 20 draws and what counts:
   a second round whose opening sentences, after the hold, still restate the first round's second
   sentence.
2. Replay each recorded second round through `OpeningHold`, and list every restated sentence it
   keeps with the words that differ.
3. Change the hold only by a rule that keeps the near misses of its tests, tested first on that
   list; if none does, close this task with the list.

## History

- 2026-11-05: filed when [R-960](960-a-round-can-repeat-an-earlier-sentence-in-other-words.md)
  closed for the one recorded form.
