# The other rewordings of a repeated sentence are not recorded

**Status:** done 2026-11-07
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

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
- 2026-11-07: done. A W04 second-round request recorded through the proxy and sent with A4's first
  round and result, 80 draws
  ([readings](../../readings/reply-repeat-in-other-words.md#the-draws-2026-11-07)), restates the
  sentence after the hold in 3: one only by `I've` for `I have`, one with `forgotten` for `removed`
  and `from my memory` left out, and one that also leaves the number out and says `your`. The rule
  written before the draws covers the first, so `OpeningHold` now reads `I've`, `I'm`, `it's` and
  `that's` as their long forms; replaying the 80 rounds, it changes only that one. The other two
  are declined: a number left out is a near miss the hold's tests keep, and a verb for another
  is outside the rule's list, so the reply shows a true sentence twice in 2 of 80.
