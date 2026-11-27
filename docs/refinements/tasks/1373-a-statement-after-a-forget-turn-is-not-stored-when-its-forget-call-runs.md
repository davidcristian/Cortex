# A statement after a forget turn is not stored when its forget call runs

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-27

A chat asked to forget in other words (`Cancel the code I gave you.`, `Get my phone number out of
there.`, `Scrap the code.`), then stated a new value in a message of its own (`My alarm code is
5528.`). Over 24 live draws on 2026-11-27 the new value was not stored in 12, each after a forget
call ran in the statement's own turn
([readings](../../readings/forget-open-from-earlier-turns.md#a-forget-in-other-words-then-a-new-value-2026-11-27)).
In 6 of them the call's text was the new value or the whole statement (`{"text": "5528"}`,
`{"text": "My alarm code is 5528."}`), it matched no row, and the turn still stored nothing:
`memory_withheld` (`memory_claim.py`) withholds every turn with a `forget_memories` run, and the
call's result tells the model the message asked to forget something. In the other 6 the call
deleted the old row, and the turn stored nothing either. In 11 of the 12 a brain note or the reply
said the new value was not kept, and the twelfth asked whether to remember it, so the loss is told.
But the person had already done what the note asks, sending the value in a message of its own.

## What to do

1. Read which runs `memory_withheld` should count when the person's own message asks to forget
   nothing (`asks_to_forget` false) and the forget was opened only by an earlier exchange. A typed
   check of the run against the store (a call that deleted no row) or of the call's text against
   the message is in scope; a wider reader of the message is not, since the forget readers are
   frozen.
2. Write the rule and the rows first: the statement stored in the draws where the call deleted
   nothing, and no stored row that holds a value a call of the same turn deleted. Draw it live with
   the old value seeded before it ships.

## History

- 2026-11-27: filed from the count of task 1193, whose draws showed it.
