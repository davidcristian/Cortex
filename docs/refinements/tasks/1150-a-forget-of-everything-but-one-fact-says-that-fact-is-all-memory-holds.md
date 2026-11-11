# A forget of everything but one fact says that fact is all memory holds

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-12

On 2026-11-12 the `cortexn20` stack stored `Remember that my card is 4111 1111 1111 4242.` and
`Remember that my gym code is 4242.` in two chats, then sent `Forget everything but my card.` (4
draws) or `Forget all but my card.` (4 draws) in a third. No draw called a forget tool. Recall
ranked only the card row as helping with the message, so the first request named only that row,
and 7 of the 8 replies said the card was the only memory stored, such as `The card number (4111
1111 1111 4242) is the only memory currently stored, so there is nothing else to forget.`, while
the gym row was stored. None of the 7 got a note. The eighth said other memories were cleared and
got `UNFORGOTTEN_CLAIM_NOTE`
([readings](../../readings/forget-keep-except.md#neighbouring-flows-on-the-live-stack-what-was-drawn)).

## What to do

1. Check the premise: is the ranker's pick, which drops rows the message does not ask about, the
   cause, or does the cortex skip the call with every row in the request too? Draw one row with
   recall set to `raw` before choosing a fix.
2. Prefer a brain-appended note after a typed check: on a turn whose message asks to forget and
   keep (`keep_words` not empty) and with no forget call, a note that is true on every turn it
   reaches, such as that nothing was deleted from memory in this turn. Write near misses first and
   replay the recorded forget strings through the check.
3. Write the rows and the pass rule into the readings before the baseline draw.

## History

- 2026-11-12: filed while closing task 1149, from its neighbouring flow draws.
