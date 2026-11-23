# A plural row word a forget message keeps after a word for all is listed

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-23

Over a locker code, a card and a phone that all end in `4242`, in unit calls through
`ForgetChosenTool`, `Forget all 4242 but the lockers.`, `Forget all 4242, the lockers stays.` and
`Forget all 4242. The lockers stays.` with the call text `4242` or `locker` delete the locker.
`Oublie tous les 4242, le casiers reste.`, `le téléphones reste` and the Spanish `el gimnasios se
queda` and `el teléfonos se queda` do the same over the French and Spanish rows. The singular
forms keep the row. This is the unsafe direction: 22 rows the message asks to keep are listed
over the 1,176 keep forms of the generator, the same count before and after the change that read
`codes` and `cards` in a part asking to forget.

The keep readers after a word for all (`after_but`, `beside`, `_restated`) compare a word with a
row word or a kind word of `forget_kinds.py`, and `lockers`, `casiers`, `téléphones`,
`gimnasios` and `teléfonos` are neither. `extends` reads such a word in a clause holding a
forget verb only, since a reader that names a row by it in any clause lists a row a keep clause
names and no reader reads (`Uită toate, cardul rămâne, dulapul rămâne.`).

## What to do

1. Write the forms above as tests first, beside the near misses `Forget all 4242 but the
   locker.` and `Forget all 4242 except the cards.`, which keep the row today.
2. Read a word of a keep clause that names no row with `extends` in the keep readers, so a row
   it names is kept. Keeping is the safe direction there, so it needs no forget verb.
3. Replay the generator with the keep forms of
   `~/.cache/cortex-run/2026-11-23/f2/forms.py`: rows the message asks to keep that are listed
   must fall to zero, and no row asked to delete may be newly kept.

## History

- 2026-11-23: filed from the close of
  [R-1286](1286-a-forget-naming-a-code-deletes-another-row-after-a-word-for-all-or-for-a-code-word-in-another-number.md),
  whose replay added the keep forms.
