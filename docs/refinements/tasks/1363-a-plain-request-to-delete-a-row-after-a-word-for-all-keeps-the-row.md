# A plain request to delete a row after a word for all keeps the row

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-26

The head rule in `_head_run` (`forget_permit.py`) reads the words after the word for all of a
forget of everything as one more run, which keeps a row it names in a role no reader reads. So
`Delete all of my card details from memory.` and `Forget everything on my card please.` keep the
card: `details` and `please` follow the row word, and no reader reads them. With the three rows
seeded the card stayed stored in 16 of 16 draws, against 0 of 16 at the run's start tree, and
every reply ended with a true note that nothing was forgotten
([readings](../../readings/forget-readers-live-draw.md#the-cost-of-the-head-rule-after-a-word-for-all)).
The replay of the rule counted these 16 rows of two test literals as its whole cost over the
generator
([readings](../../readings/forget-everything-unread-forms.md#heads-of-more-than-one-word-2026-11-26)).

## What to do

1. Count over the generator, the recorded messages and the mixed sets how many forgets of
   everything name a row after a placing word with no keep verb after it, as `all of my card
   details` and `everything on my card please`, against the kept forms such as `all of it the card
   stays`.
2. Find a rule with no word list that reads such a run as the scope of the forget, with unsafe
   cases at 0 over every set, state its cost, and draw it with the rows seeded.

## History

- 2026-11-26: filed from the seeded draw of the head rule's cost.
