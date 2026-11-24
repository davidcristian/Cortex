# The Romanian word for all is not read by the forget card

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-24

The Romanian cell of the word for all in `FORMS` (`forget_forms.py`) is empty, so `Uită toate
4242.` keeps every row where `Forget all 4242.` deletes all three. Filled alone, `toate` deletes
441 rows asked to delete over the generator's Romanian messages and lists 10 rows asked to keep,
each named in the plural in a keep clause (`Uită toate 4242, cardurile rămâne.`), and 36 not
asked for, each beside an unread `doar`, `și` or `tot` ([readings](../../readings/forget-form-cells.md#the-cells-replayed-one-at-a-time-2026-11-24)). The plural is
[task 1304](1304-a-romanian-plural-row-word-in-a-forget-message-names-no-row.md); the words for
all that another language shares (`tot`, `alles`, `todo`) are
[task 1230](1230-a-forget-of-everything-in-a-form-the-card-does-not-take-as-one-lists-a-row-its-message-keeps.md).

## What to do

1. Once task 1304 reads a Romanian plural, fill the cell in a copy and replay it over the
   generator. Fill it when no row asked to keep is listed.
2. The 36 rows beside `doar` wait on
   [task 1326](1326-a-word-for-only-is-read-by-the-forget-card-in-english-alone.md), or on a
   reading that keeps every row of a message holding an unread word for only.

## History

- 2026-11-24: filed from the survey of [task 1221](1221-the-forms-the-forget-card-reads-in-english-are-not-all-read-in-the-other-four-languages.md).
