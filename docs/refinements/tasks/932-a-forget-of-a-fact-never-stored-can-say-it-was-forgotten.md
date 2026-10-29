# A forget of a fact never stored can say it was forgotten

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-10-29

On the `cortexn10` stack, "Please forget my passport number." in a new chat, with no memory
holding a passport, failed row F5 of
[forget-chosen-memories.md](../../readings/forget-chosen-memories.md#the-pass-rule) in 6 of 15
draws on the brain that still showed the no-match card and 5 of 15 on the one that shows none
([readings](../../readings/forget-that-deletes-nothing.md#f5-before-and-with-the-change-the-draws-2026-10-29)).
Six replies said the passport number was forgotten, cleared or the request processed, without
saying nothing was found; five asked the person for "a specific number" to forget. Every call
returned the no-match result, which says nothing was forgotten and there is no need to ask for the
value, followed by `FORGET_NOT_KEPT_NOTE`. On 2026-10-28, before that note was added to every
result of the tool, the row passed in 5 of 5.

## What to do

1. Write rows and a rule before any draw: F5, 15 draws each, with the shipped result and with the
   note left off the no-match result, to measure whether the note causes the failures.
2. If it does, change the result text the model reads for a forget that deleted nothing, measured
   on F5 and on the not-kept rows of
   [remember-on-a-turn-not-kept.md](../../readings/remember-on-a-turn-not-kept.md), since the note
   is what keeps a reply on such a turn from claiming a fact was kept.

## History

- 2026-10-29: filed from the F5 draws of the forget that shows no card.
