# A forget naming a card lists a phone ending in the same group

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-13

Over `User: Remember that my card is 4111 1111 1111 4242.` and `User: Remember that my mobile
phone is 0721 555 4242.`, `Forget the card ending in 4242.` with call text `4242` lists and
deletes both rows, at the start build and after the kind words, from the calling chat and a new one
([readings](../../readings/forget-kind-and-value-names.md#replay-through-the-start-build-and-the-change)).
Neither row holds `4242` whole, so the last group keep (`_ends` in `forget_inside.py`) keeps
neither, and `unnamed` keeps only a row whose request holds the call's value as a value of its
own, which `4242` is in neither.

## What to do

1. Write the case as a test, with near misses: `Forget the card ending in 4242.` over two cards
   ending in 4242 lists both, and `Forget 4242.` over the card and the phone lists both.
2. Decide whether a row holding the value only as a last group, which no word or kind of the
   message names, is kept when another match is named, then replay the recorded strings.

## History

- 2026-11-13: filed from the replay of the kind words across languages, task
  [1158](1158-a-forget-in-one-language-keeps-a-row-stored-in-another.md).
