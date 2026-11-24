# The old value note reads a second value or a second sentence as a new value

**Status:** done 2026-11-24
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

`_replaced` (`memory_old_value.py`) takes the value of `FACT_VALUE` (`fact_statement.py`): at most
four words that hold no comma, colon or question mark. A full stop is allowed inside a word, so
the value can run past a sentence end, and any word can come first. Run on 2026-11-15 with no
model, each message beside the row shown:

| Message | Stored row | Old value note |
| --- | --- | --- |
| `My door code is also 7319.` | `Remember that my door code is 1987.` | `1987` |
| `My pet is Rex. Room 12.` | `My pet is 2 years old.` | `2 years old` |
| `My PIN is 4242 off the record.` | `Remember that my PIN is 1987.` | `1987` |

The first gives the fact a second value, the second states no value with a digit for the fact,
and the third asks that the new value not be kept. In each the note calls the stored value the
one the message corrects. The same three readings follow a request to store or remember, except
the third, which `asks_not_kept` already stops there.

## What to do

1. Write tests first: the three messages above name nothing; `My alarm code is now 5528.` and
   `My alarm code is 5528. Thanks!` still name `4826`.
2. End the value at a sentence end, and give no note when the value opens with a word that adds
   (`also`, `too` after it) or when `asks_not_kept` reads the message. Decide each on the replay
   and not on a longer word list.
3. Replay every string literal of the brain's tests and every backticked string of
   `docs/readings/` through both builds and count the notes dropped; each must be one of the three
   forms above.

## History

- 2026-11-15: filed from the replay of the request reader (task 1198), which reads a bare
  statement as before.
- 2026-11-24: done. The three messages still named an old value, and reading the first
  sentence alone opens `My alarm code is 5528. Wait, that is wrong.`, so step 1's `5528. Thanks!`
  now names nothing. `_replaced` reads a message of one sentence only, and each value less `now`
  or `actually` at either end only when it opens with a digit or a capital letter and its other
  words that are neither match the old value's, rather than a longer word list. The replay and its
  cost, 9 messages that lose a true note (`on 12 May`, `at 8`, `Thanks!`), are in the
  [readings](../../readings/forget-refused-statement-old-row.md#a-second-value-or-a-second-sentence-2026-11-24).
