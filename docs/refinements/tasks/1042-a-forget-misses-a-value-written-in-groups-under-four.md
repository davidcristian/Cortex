# A forget misses a value written in groups under four characters

**Status:** done 2026-11-10
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

`value_searches` in `memory_values.py` finds the rows that restate a value through `find_text`,
which matches text literally, by the value as written, by its letters and digits alone and by each
four consecutive characters of them. A row writing the value only in groups under four characters, such as
`015 123 456 789` for `0151 2345 6789`, contains none of those texts, so the card does not list it
and the holding count after the delete does not count it: the row stays, which is the safe side
for a destructive card, but no `NUMBERS_LEFT_NOTE` tells the person it remains.

## What to do

1. Add a `MemoryStore` method that finds rows whose text, with ` ./-` removed, contains a key, case
   ignored: the fake compares the stripped text, the Postgres adapter
   `strpos(lower(regexp_replace(text, '[ ./-]', '', 'g')), $1) > 0`. Write its check in
   `memory_contract.py` so the fake and the live adapter pass the same test, and update the test
   doubles that implement the port.
2. Use it in `_repeating` and `_holding` in place of the windows, keeping `_repeats` as the filter,
   and keep the near-miss tests of `test_forget_value_separators.py` green.

## History

- 2026-11-08: filed when the windows search closed
  [1020](1020-a-forget-card-misses-a-value-restated-with-other-separators.md). Reproduced at unit
  level (`SCRATCH/slot7/probe.py`): rows "my phone number is 0151 2345 6789" and "Your phone is
  015 123 456 789", call text `phone number` or `0151 2345 6789`: the card lists 1 row, and the
  result says no exchange contains that text with `numbers_left` false.
- 2026-11-10: done. `MemoryStore.find_value` matches a value against each row's text with spaces,
  dots, slashes and hyphens removed from both, case ignored, and a value with nothing left finds no
  row; the fake, `PgVectorMemoryStore` and the test doubles implement it, and its check in
  `memory_contract.py` passed on the fake and live on the night's stack Postgres. `_repeating` and
  `_holding` search by it in place of `value_searches`, which is removed, and `_repeats` and the
  digit run filter still drop a longer value. This also closed task 1048.
