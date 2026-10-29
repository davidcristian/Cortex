# A request to remember can show a forget card that matches nothing

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-10-29

On the `cortexn10` stack, "Remember that my card number is 4242 4242 4242 4242." called
`forget_memories` in 10 of 40 new chats, and the 14 other requests to remember of R14 in 8 of 28
([readings](../../readings/remember-on-a-turn-not-kept.md#the-draws-of-the-change-2026-10-29)).
Each call shows the person a forget card for the fact they asked to keep, and in the earlier draws
every such card said no remembered exchange matched
([readings](../../readings/forget-card-on-remember.md#the-forget-of-a-text-on-a-request-to-remember-the-draws-2026-10-29)).
The turn is not kept whether the card is approved or denied, and since `UNKEPT_CLAIM_NOTE` the
reply says so when it claims otherwise. A sentence in the tool's description saying it is never
called on a request to remember failed its rule there.

## What to do

1. Read `ForgetChosenTool.card` and the dispatcher's card path, and decide whether a call whose
   `find_text` matches nothing can return its no-match result without a card, since nothing waits
   for approval. The turn must stay unrecorded and the result must still say nothing was removed.
2. Write rows and a rule before any draw: RC and R14 as in the readings, counting the cards shown,
   with forget requests whose value is stored as the rows that must still show one.

## History

- 2026-10-29: filed from the draws of the reply note on a turn that is not kept.
