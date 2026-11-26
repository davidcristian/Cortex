# A word for only the card leaves unread lists a row asked to keep

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-26

The forget card reads a word for only (`alone` in `forget_only.py`) only in English and only in a
run read as a limit. Over the 3,420 messages of the word for only generator in five languages
(`onlygen.py` in `~/.cache/cortex-run/2026-11-26/f5/`), the card lists 324 rows asked to keep
([readings](../../readings/forget-form-cells.md#a-word-for-only-beside-a-call-naming-a-row-2026-11-26)):

- 300 in French, German, Spanish and Romanian, where the cells of `seulement`, `nur`, `solo` and
  `doar` are empty, 24 of them on the call text `4242` itself, as the card on `Oublie 4242, la
  carte aussi, seulement le téléphone.`;
- 24 in English, on a call text naming the locker beside the value, in a run whose first word is
  a word for and (`Forget 4242 and only the phone.`) or before the value (`Forget only the phone
  4242.`).

## What to do

1. State one rule that keeps every row a reading of a word for only leaves out in these forms, and
   count over the generator and every other set the rows asked to delete it keeps.
2. Replay each filled cell of `FORMS` as the reader rules say, and draw the change with the rows
   seeded.

## History

- 2026-11-26: filed from the generator of the word for only, after the English call texts naming a
  row beside the value were read.
