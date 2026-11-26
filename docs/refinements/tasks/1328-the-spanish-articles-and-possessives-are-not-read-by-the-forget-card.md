# The Spanish articles and possessives are not read by the forget card

**Status:** declined 2026-11-26
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

The Spanish cell of the word for the or my in `FORMS` (`forget_forms.py`) holds `la` alone;
`el`, `los`, `mi` and `mis` add a row only beside an adding word, and the Spanish one is not
read. Filled together with `también`, the four words delete 180 more rows asked to delete than
`también` alone (1,256 against 1,076), list no row asked to keep, and list 4 more not asked for,
each beside an unread `solo` ([readings](../../readings/forget-form-cells.md#the-cells-replayed-one-at-a-time-2026-11-24)).

## What to do

1. Fill the four words with `también`
   ([task 1327](1327-the-spanish-and-romanian-adding-words-are-not-read-by-the-forget-card.md)),
   after a replay of both that lists no row not asked for.

## History

- 2026-11-24: filed from the survey of [task 1221](1221-the-forms-the-forget-card-reads-in-english-are-not-all-read-in-the-other-four-languages.md).
- 2026-11-26: declined at the freeze of the forget message readers ([ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md) decision 7): its remedy fills a `FORMS` cell and its counts are over generated messages. 180 rows asked to delete stay kept beyond those of `también` ([readings](../../readings/forget-freeze.md#forms-left-unread-at-the-freeze-2026-11-26)).
