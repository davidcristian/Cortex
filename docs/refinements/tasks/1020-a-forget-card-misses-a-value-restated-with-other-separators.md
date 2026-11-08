# A forget card misses a value restated with other separators

**Status:** done 2026-11-08
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

`whole_values` keys each value by its letters and digits alone, so `0151 2345 6789` and
`015123456789` share one key. `_repeating` in `memory_forget_chosen.py` then asks the store for
rows holding the value with `find_text(form)`, where `form` is the value as the found row wrote it,
and both stores match that text literally (`find_text` in `fakes_memory.py` and the
`FIND_SCOPED` query of `cortex_memory`). A row writing the same number with other separators, or
none, never comes back from the store, so the key comparison in `_repeats` never sees it, and the
restatement stays after the forget. The token reader before it missed these rows too. The result
of the delete counts such a row, since `digit_runs` compares the remaining rows by their digits
alone, and a reply saying the number was forgotten ends with `NUMBERS_LEFT_NOTE`; the card still
does not list the row.

Reproduction, unit level (`SCRATCH/slot16/probe.py`): rows "my phone number is 0151 2345 6789"
and "Call my phone at 015123456789 later", call text `phone number`: the card lists 1 row. The
same with the forms swapped: 1 row.

## What to do

1. Write both pairs as tests first, and write down whether `+49 151 2345 6789` is the same value
   as `0151 2345 6789`; a longer number that only contains the key is a near miss that stays out.
2. Search the store by a form that ignores separators, such as a `find_digits` port method whose
   Postgres adapter compares `regexp_replace(text, '[ ./-]', '', 'g')`, with the same contract
   test for the fake and the adapter, and a manual `ALTER TABLE` line only if an index is added.

## History

- 2026-11-07: filed by the second audit of the night; reproduced at unit level, no turn sent.
- 2026-11-08: done without a port change. `value_searches` (`memory_values.py`) finds the rows by
  the value as written, by its letters and digits alone and by each four consecutive characters of them, and
  `_repeats` still requires the whole value, so the card lists both pairs above, and a text that is
  itself the value lists them too. `+49 151 2345 6789` is not the same value: its digits differ, so
  it stays off the card. Near misses stay (another number sharing a prefix, a longer number, a year
  or date, the digits split across two values). The holding count uses the same searches. Replayed
  through the start hash and this build, the 49 calls of the 46 recorded forget turns of
  2026-11-07 get the same cards, results and rows left. A value written only in groups under four
  characters is still missed: [1042](1042-a-forget-misses-a-value-written-in-groups-under-four.md).
