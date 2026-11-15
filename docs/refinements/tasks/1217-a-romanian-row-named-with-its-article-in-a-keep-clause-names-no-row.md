# A Romanian row named with its article in a keep clause names no row

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-15

Over the rows `Ține minte că codul de la dulap este 4242.`, `Ține minte că cardul meu este 4111
1111 1111 4242.` and `Ține minte că telefonul meu este 0721 555 4242.`, with the call text `4242`,
`Uită cardul 4242, păstrează cardul și dulapul.` and `Uită cardul 4242 exceptând cardul exceptând
dulapul.` list the card, which the message asks to keep. `_restated` (`forget_inside.py`) keeps a
row named to forget and again in a keep clause when every other word of the clause names another
row. The row holds `dulap` and the message says `dulapul`, the same noun with its article, and
`names` (`forget_kinds.py`) compares whole words, so `dulapul` names no row and the clause reads
as one naming another fact. Of 42,356 generated messages 35 list such a row, all Romanian. The
same comparison keeps a row unnamed wherever a reader matches a Romanian noun written with its
article against a row holding it without one.

## What to do

1. Write tests first: the two messages above keep the card, and a keep clause naming the card
   beside a word of no row still deletes it.
2. Count, over the generator in `/home/david/.cache/cortex-run/2026-11-15/slot7/` and every
   Romanian literal of the brain's forget tests, the rows each reader reads differently when a
   word of the message names a row holding the same word less a final `ul`, `le`, `a` or `ua`.
   Each row newly listed must be one the message asks to delete.
3. Check the near misses first: a word that ends in an article form and is another noun must
   keep its row unread.

## History

- 2026-11-15: filed with the change that keeps a row a keep clause names beside another row
  ([readings](../../readings/forget-keep-except.md#the-role-of-a-row-named-after-the-value-2026-11-15)).
