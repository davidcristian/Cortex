# A forget of every row holding a code keeps a card ending in it

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-12

Over `User: Remember that my card is 4111 1111 1111 4242.` and `User: Remember that my gym code is
4242.`, the messages `Forget everything with 4242.`, `Forget every 4242.`, `Forget all of 4242.`
and `Forget 4242 everywhere.` with call text `4242` delete only the gym row in 12 of 16 cases (both
row orders, the storing chat or a new one); the start build deleted both
([readings](../../readings/forget-keep-plain-replay.md#two-calls-and-every-row)). `_ends`
(`forget_inside.py`) keeps the card's last group when a row holds the code whole and the message
names no word only the card has, and reads no word asking for every row, which `_quantifies`
(`forget_unnamed.py`) reads for `unnamed`. The inside note names the kept card, so the person sees
it.

## What to do

1. Decide whether a card ending in a code is a row holding that code for a forget of every row:
   the card is named `the card ending in 4242`, and keeping it is the safe side of the card.
2. If it is, write the four messages as tests with near misses (`Forget every gym code 4242.`
   keeps the card), let `_quantifies` stop the keep in `_ends`, and replay the strings of the
   readings through the old and new code.

## History

- 2026-11-12: filed from the replay of plain forgets through the destructive card.
