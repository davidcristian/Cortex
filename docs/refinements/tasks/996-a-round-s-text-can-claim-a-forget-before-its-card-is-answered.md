# A round's text can claim a forget before its card is answered

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-07

In 1 of the 15 draws of M05 on 2026-11-07
([readings](../../readings/forget-after-delete-provoked.md#the-draws-2026-11-07)), the first round
streamed "I've updated your phone number to 0699000000 and removed the old number from my memory."
beside its `forget_memories` call, so the person read that the old number was removed before the
card asking to delete it was shown. Every card was approved in that run, so the claim came true;
whether a reply corrects it after a denied card is not measured. The turn log is `turn-a4.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/37073e3c-5ca6-42f6-aae1-df9e67b0e4db/scratchpad/slot2/`.
`OpeningHold` (`round_opening.py`) holds a round's opening sentences only while they repeat what an
earlier round streamed, so it never holds a first round.

## What to do

1. Write a row of a forget request with every card denied, and a rule counting the replies whose
   text before the card says the value was removed, into the readings before a baseline.
2. If the form comes, try first a note the brain appends after a denied card when a round's text
   claimed the forget, before holding a round's text until the card is answered.

## History

- 2026-11-07: filed from the draws of the forget after a delete in
  [R-969](969-a-forget-of-the-old-value-can-match-nothing-and-say-none-is-stored.md).
