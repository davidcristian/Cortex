# Recall leaves out the rows a forget of everything but one fact asks to delete

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Verified:** 2026-11-15

On 2026-11-12 the `cortexn20` stack stored a card row and a gym code row, then sent
`Forget everything but my card.`. With the default `judge` recall the first request held only the
card row and the cortex made no forget call in 8 of 8 draws. With `CORTEX_MEMORY_RECALL=raw` the
first request held both rows and the cortex called `forget_memories` in 3 of 3
([readings](../../readings/forget-keep-no-call.md#recall-set-to-raw-2026-11-12-what-was-drawn)).
The rank orders the pool by what helps with the message, and the rows a keep clause asks to delete
are the ones the message does not name. Since 2026-11-12 `UNCALLED_FORGET_NOTE` tells the person
that nothing was deleted on such a turn.

On 2026-11-15 the `cortexn23` stack drew that message again and `Forget all 4242 except the card.`
over a locker code, a card and a phone sharing `4242`. The tool was listed on every turn. The first
request held the row to delete in 1 of 6 draws, the only draw with a forget call, and 5 replies were
untrue: the card is all memory holds, or, on `Forget all 4242 apart from the card.` earlier that
day, "My forget tool deletes every memory that includes the specified text". A build that added the
rows the request reaches to the first request held the row to delete in 6 of 6 draws and made a
forget call in 6 of 6, and left that row stored in 5 of 6, so it was not committed
([readings](../../readings/forget-keep-no-call.md#rows-a-forget-request-holds-2026-11-15-what-was-drawn)).

## What to do

1. Build the card reading of
   [task 1222](1222-a-forget-of-every-row-but-one-keeps-a-row-the-call-names-in-the-rows-own-words.md)
   first or in the same change: beside a keep clause (`except`, `everything but`) the rows alone
   turn "the card is all I hold" into "I forgot it" over a row still stored. On
   `Forget all 4242 apart from the card.`, which the card reads with no keep clause, the rows alone
   deleted the locker and phone rows and kept the card in 2 of 2 draws.
2. Add the rows again: on a message `asks_to_forget` or `asks_to_forget_keeping` reads,
   `assemble_inference_messages` adds after the ranked rows at most 5 the rank left out, from
   `MemoryRecaller.find_value` for each `whole_values` key of the message, or from a search of the
   message with no policy when it names no value beside a fact to keep. Render them with the
   ranked rows, so a tainted row is fenced and `fit_recalled` cuts each. A message asking to forget
   nothing must read the store once.
3. Draw rows e1 and v1 of the readings under the rule written there, and count what the person
   ends up with.

## History

- 2026-11-12: filed from the draw with recall set to `raw` made while adding
  `UNCALLED_FORGET_NOTE`.
- 2026-11-15: the premise was confirmed from the recording proxy's log and the rows were added in
  a build that was drawn and not committed, since the rule failed on what the person ends up with.
  Filed
  [task 1222](1222-a-forget-of-every-row-but-one-keeps-a-row-the-call-names-in-the-rows-own-words.md)
  and
  [task 1223](1223-a-reply-saying-rows-were-removed-after-calls-that-kept-every-row-gets-no-note-that-nothing-was-forgotten.md).
