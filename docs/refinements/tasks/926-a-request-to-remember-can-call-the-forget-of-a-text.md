# A request to remember can call the forget of a text

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-10-29

"Remember that my card number is 4242 4242 4242 4242." called `forget_memories` with the number
in 9 of 55 draws on the `cortexn10` stack, each card saying that no remembered exchange matched
([readings](../../readings/forget-chosen-memories.md#a-forget-and-a-new-fact-the-draws-2026-10-29)).
`record_exchange` (`turn_output.py`) skips every turn whose model named the forget, so the fact
the person asked to keep was not stored, while 8 of the 9 replies said the number was noted. The
14 other remember rows called it in 2 of 28 draws with the shipped description, and five of six
such replies across tonight's runs said the fact was noted, though the result of a denied card
now ends with the note that nothing in the message is kept
([readings](../../readings/forget-card-on-remember.md#the-forget-of-a-text-on-a-request-to-remember-the-draws-2026-10-29)).

The skip itself is right: a forget that matched nothing may still name a value the person wants
gone, as the passport row of the same readings shows.

## What to do

1. The rows and the next rule are written in
   [forget-card-on-remember.md](../../readings/forget-card-on-remember.md#the-forget-of-a-text-on-a-request-to-remember-the-draws-2026-10-29):
   RC and R14 with every card denied, counting the replies of the draws that call the forget which
   say the fact was kept.
2. Draw the baseline, then the note naming the call rather than the request, and ship it only if
   that rule passes.

## History

- 2026-10-29: filed from the draws of task 922 on the `cortexn10` stack.
- 2026-10-29: the description sentence that the tool is never called on a request to remember
  failed its rule: RC called the forget in 2 of 20 draws and R14 in 4 of 28, against at most 1
  and 0. The description is unchanged; the next rule is the note's wording.
