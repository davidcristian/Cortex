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

The no-match card is one of four that `ForgetChosenTool._choose` returns for a call that deletes
nothing whatever the answer: no text named (`_NOTHING_NAMED`), the store unavailable (`_NO_STORE`),
more than `FORGET_CHOSEN_LIMIT` matches (`_TOO_MANY`) and no match (`_NO_MATCH`). The dispatcher
cannot skip one today: `ToolDispatcher._confirmed` asks the confirmer whenever a call needs
confirmation, and with no confirmer it answers `UNANSWERED` before `card` runs.

1. Let a `RecordCard` say that nothing waits for approval, for example `card` returning `None`,
   and have `_confirmed` call `card` first and then run the call without asking. `card` still
   stores the call's reason in `_shown`, so `invoke` returns it with `FORGET_NOT_KEPT_NOTE`, and
   the turn stays unrecorded (`memory_withheld`). Decide in ADR-0075 whether the other three
   reasons skip the card too. What the model reads changes only where the card was denied: the
   reason replaces `USER_DECLINED_MSG`.
2. Write rows and a rule before any draw: RC and R14 as in the readings, counting the cards shown
   and the replies that claim a fact was kept, with forget requests whose value is stored as the
   rows that must still show one.

## History

- 2026-10-29: filed from the draws of the reply note on a turn that is not kept.
