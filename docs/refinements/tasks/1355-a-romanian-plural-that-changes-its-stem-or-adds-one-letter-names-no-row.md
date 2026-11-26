# A Romanian plural that changes its stem or adds one letter names no row

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-26

Over the rows `Ține minte că codul de la dulap este 4242.`, `Ține minte că cardul meu este 4111
1111 1111 4242.` and `Ține minte că telefonul meu este 0721 555 4242.`, `Uită telefoanele.`,
`Uită telefoane.`, `Uită carduri.` and `Uită coduri.` name no row, so the call text decides: 64
rows not asked for are listed over the plural set of 640 cases
([readings](../../readings/forget-romanian-plural.md)). `grows` (`forget_kinds.py`) needs a word
three letters longer than the row word, so `carduri` of `cardul` is one letter short, and
`telefoane` changes the stem `telefon`.

Reading a word one or two letters longer this way would also read `remembered` as naming every
English row by `remember`, which narrows nothing and lets a call list rows the message does not
ask for. With
`unnamed` (`forget_unnamed.py`) a call text of `4242` keeps every row for `Uită cardurile.`, where
`Uită cardul.` deletes the card.

## What to do

1. Write the four forms as tests first, and `Forget what you remembered about my card.` with the
   call text `4242`, which deletes the card alone.
2. Find a reading of these forms that adds no word list and lists no row the plural does not
   name, replayed over the plural set in `~/.cache/cortex-run/2026-11-26/f4/` (`plgen.py`) and
   the word pairs, or decline with the 64 rows it leaves.

## History

- 2026-11-26: filed from the close of
  [task 1304](1304-a-romanian-plural-row-word-in-a-forget-message-names-no-row.md).
