# The Spanish and Romanian adding words are not read by the forget card

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-24

The Spanish and Romanian cells of the adding word in `FORMS` (`forget_forms.py`) are empty, so
`Olvida 4242, la tarjeta también.` and `Uită 4242, cardul de asemenea.` keep every row, where
`Forget 4242, the card too.` deletes the card and the locker code. Filled alone, `también`
deletes 1,076 rows asked to delete, lists no row asked to keep, and lists 36 not asked for: 28
beside an unread `solo` (`Olvida 4242, el teléfono también, solo la tarjeta.`) and 8 in a form
HEAD already lists without it ([readings](../../readings/forget-form-cells.md#the-cells-replayed-one-at-a-time-2026-11-24)). `de asemenea` is two words, a cell holds one word per entry,
and `și` is the word for and.

## What to do

1. Fill `también` once
   [task 1326](1326-a-word-for-only-is-read-by-the-forget-card-in-english-alone.md) reads `solo`,
   after a replay that lists no row not asked for beside it.
2. Read `de asemenea` as one adding word with no new word list, as tests first, and replay it.

## History

- 2026-11-24: filed from the survey of [task 1221](1221-the-forms-the-forget-card-reads-in-english-are-not-all-read-in-the-other-four-languages.md).
