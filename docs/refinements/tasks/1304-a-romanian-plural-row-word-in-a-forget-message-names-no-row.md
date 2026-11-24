# A Romanian plural row word in a forget message names no row

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-24

Over the Romanian rows `Ține minte că codul de la dulap este 4242.`, `Ține minte că cardul meu
este 4111 1111 1111 4242.` and `Ține minte că telefonul meu este 0721 555 4242.`, in unit calls
through `ForgetChosenTool`, `Uită codurile.`, `Uită cardurile.`, `Uită dulapurile.`,
`Uită telefoanele.` and the same after `toate` delete the row the call text names, as any message
naming no stored row does: 24 rows the message does not ask for over the generator. `extends`
(`forget_kinds.py`) reads a word less one or two letters, and these plurals add more (`cardurile`
of `cardul`, `dulapurile` of `dulap`) or change the stem (`telefoanele` of `telefonul`).

The card shows each row before it is deleted, so this is the direction a message naming no row
already takes. A table of Romanian endings would be a word list; `bare` already reads the
article `ul`.

## What to do

1. Write the forms above as tests first, beside `Uită dulapul.`, which names the locker row.
2. Find one reading of a Romanian plural that adds no word list, or decline with the count of
   rows it leaves, which the replay in `~/.cache/cortex-run/2026-11-23/f2/` gives.

## History

- 2026-11-23: filed from the close of
  [R-1286](1286-a-forget-naming-a-code-deletes-another-row-after-a-word-for-all-or-for-a-code-word-in-another-number.md).
