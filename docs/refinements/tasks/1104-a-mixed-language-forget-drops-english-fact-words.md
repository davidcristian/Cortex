# A mixed language forget drops English fact words

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-09

The forget reader drops the function words of the one language `message_language` picks. In a
message that mixes German and English, English fact words that are German function words stop
naming rows. Unit calls of `unnamed` on 2026-11-09, rows `the den alarm code is 7319` and `my
hat locker is 7319` among others: `Vergiss bitte den code 7319 vom hat, keep the den` reads as
German, so `den` in the keep clause names nothing and every row is listed, the den row with
them. Mixed messages are rare in the recorded draws; none of them is one.

## What to do

1. Write the message above as a test first, beside a German message whose `den` must still
   name nothing (`Vergiss den Türcode 7319.`).
2. Drop a function word only from a clause whose own words are in that language, then replay
   every recorded forget string through the old and new reader.

## History

- 2026-11-09: filed from unit calls in the third audit of the night (`probe2.py` in
  `/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot18/`).
