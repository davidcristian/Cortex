# A forget by a short value deletes a row holding it inside a longer one

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-12

On 2026-11-12 the `cortexn20` stack stored `Remember that my card is 4111 1111 1111 4242.` and
`Remember that my gym code is 4242.`, then sent `Forget my gym code.` in a new chat. In one of
three draws the cortex called `forget_memories` with the text `4242`, the card listed both rows,
and the approved card deleted the card row too
([readings](../../readings/forget-keep-no-call.md#a-forget-with-no-keep-clause-what-was-drawn)).
`unnamed` (`forget_unnamed.py`) keeps a row only when its request holds the value as a whole value,
and the card row holds `4242` only as the last group of a longer number. The inside rule keeps such
a row when no row holds the value whole, but here the gym row does. The destructive card's safe
direction keeps rows, and the message names no word of the card row.

## What to do

1. Write the rows as unit tests first: the two rows above, the text `4242`, and the messages
   `Forget my gym code.`, `Forget the code 4242.` and `Forget the card ending in 4242.`; only the
   last may list the card row.
2. Keep a row that holds the text only inside a longer value and that the message names no word
   of, also when another row holds the text whole, then replay the recorded forget strings.

## History

- 2026-11-12: filed from the draws of the note on a forget with no keep clause and no call.
