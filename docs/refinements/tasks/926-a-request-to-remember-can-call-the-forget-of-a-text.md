# A request to remember can call the forget of a text

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-10-29

"Remember that my card number is 4242 4242 4242 4242." called `forget_memories` with the number
in 6 of 35 draws on the `cortexn10` stack, each card saying that no remembered exchange matched
([readings](../../readings/forget-chosen-memories.md#a-forget-and-a-new-fact-the-draws-2026-10-29)).
`record_exchange` (`turn_output.py`) skips every turn whose model named the forget, so the fact
the person asked to keep was not stored, while each reply said the number was noted. The driver
approved every card; a declined call is a named call too, so a Deny changes nothing.

The skip itself is right: a forget that matched nothing may still name a value the person wants
gone, as the passport row of the same readings shows.

## What to do

1. Write rows and a pass rule first: the remember messages of
   [forget-card-on-remember.md](../../readings/forget-card-on-remember.md) and the card number
   above, five draws each, counting the calls to `forget_memories`.
2. Then try the tool's description, saying it is never called on a request to remember, and ship
   it only if those rows pass and rows F3 and F5 of the same readings still pass by their rule.

## History

- 2026-10-29: filed from the draws of task 922 on the `cortexn10` stack.
