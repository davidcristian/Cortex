# A Romanian row named with its article in a keep clause names no row

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-21

Over the rows `Ține minte că codul de la dulap este 4242.`, `Ține minte că cardul meu este 4111
1111 1111 4242.` and `Ține minte că telefonul meu este 0721 555 4242.`, with the call text `4242`,
`Uită cardul 4242, păstrează dulapul și cardul.` and `Uită cardul 4242 exceptând dulapul exceptând
cardul.` list the card, which the message asks to keep. `_restated` (`forget_inside.py`) keeps a
row named to forget and again in a keep clause unless a word before its name in the clause names
no row. The row holds `dulap` and the message says `dulapul`, the same noun with its article, and
`names` (`forget_kinds.py`) compares whole words, so `dulapul` names no row and the clause reads
as one naming another fact. Of 42,356 generated messages 14 list such a row, all Romanian. The
same comparison keeps a row unnamed wherever a reader matches a Romanian noun written with its
article against a row holding it without one.

## What to do

1. Write tests first: the two messages above keep the card, and a keep clause naming the card
   after a word of no row, as `Forget the card 4242, I don't need the card.`, still deletes it.
2. Count, over the generator in `/home/david/.cache/cortex-run/2026-11-15/slot7/` and every
   Romanian literal of the brain's forget tests, the rows each reader reads differently when a
   word of the message names a row holding the same word less a final `ul`, `le`, `a` or `ua`.
   Each row newly listed must be one the message asks to delete.
3. Check the near misses first: a word that ends in an article form and is another noun must
   keep its row unread.

## History

- 2026-11-15: filed with the change that keeps a row a keep clause names beside another row
  ([readings](../../readings/forget-keep-except.md#the-role-of-a-row-named-after-the-value-2026-11-15)).
- 2026-11-21: corrected. `_restated` now keeps a row a keep clause names again before a word
  naming no row ([R-1216](1216-a-keep-clause-naming-the-row-to-forget-beside-a-word-for-only-lists-it.md)),
  so `păstrează cardul și dulapul` and `exceptând cardul exceptând dulapul` keep the card and the
  generator's count fell from 35 to 14. The messages above name `dulapul` before the card.
