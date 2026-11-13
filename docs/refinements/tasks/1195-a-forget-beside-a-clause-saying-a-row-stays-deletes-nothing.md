# A forget beside a clause saying a row stays deletes nothing

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-14

With the rows `Remember that my card is 4111 1111 1111 4242.` and `Remember that my mobile phone is
0721 555 4242.` stored, the message `Forget the card 4242, my phone stays.` deleted no row in 2 of
2 stack draws ([the remark readings](../../readings/forget-remark-about-the-value.md#a-clause-adding-a-row)).
In one the cortex made no call and asked whether to forget the whole phone number; in the other it
sent a forget call whose text no row holds, and the unmatched note said nothing was deleted. The
card the person asked to forget stays, which is the safe direction, and the reply says so, so the
person can ask again. The card reader is not involved: no call reached it with the text `4242`.

## What to do

1. Draw the message and `Forget the card 4242.` alone on one build, enough times to tell whether
   the clause `my phone stays` lowers how often a call sends `4242` or the card's whole value.
2. If it does, decide on that evidence between a prompt line and leaving it, since the reply
   already says that nothing was deleted.

## History

- 2026-11-14: filed from the live draws for task 1192; logs `draw.log` and `draws.jsonl` in
  `/tmp/claude-1000/-home-david-Files-Git-Cortex/11450320-079c-401d-9f26-43a763a369b6/scratchpad/slot3/`.
