# Recall leaves out the rows a forget of everything but one fact asks to delete

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Verified:** 2026-11-12

On 2026-11-12 the `cortexn20` stack stored a card row and a gym code row, then sent
`Forget everything but my card.`. With the default `judge` recall the first request held only the
card row and the cortex made no forget call in 8 of 8 draws. With `CORTEX_MEMORY_RECALL=raw` the
first request held both rows and the cortex called `forget_memories` in 3 of 3
([readings](../../readings/forget-keep-no-call.md#recall-set-to-raw-2026-11-12-what-was-drawn)).
The rank orders the pool by what helps with the message, and the rows a keep clause asks to delete
are the ones the message does not name. Since 2026-11-12 `UNCALLED_FORGET_NOTE` tells the person
that nothing was deleted on such a turn.

## What to do

1. Write rows and a rule first: whether a forget message with a keep clause should recall the
   whole pool unranked, or the ranked rows plus those its forget words reach, and count forget
   calls and the rows the request holds per build.
2. A call made this way keeps every row today, since the forget part names none, so measure what
   the person ends up with, not only whether a call is made.

## History

- 2026-11-12: filed from the draw with recall set to `raw` made while adding
  `UNCALLED_FORGET_NOTE`.
- 2026-11-15: `Forget all 4242 except the card.` over a locker code, a card and a phone sharing
  `4242` made no forget call in 2 of 2 draws on the `cortexn23` stack, and each reply said the
  card is the only memory holding `4242`
  ([task 1215](1215-a-forget-of-every-value-but-one-row-is-refused-with-an-untrue-account-of-the-tool.md)).
