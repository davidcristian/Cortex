# A new value of a fact stated in another language names no old value

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-15

`_replaced` (`memory_old_value.py`) reads the stated fact and the stored row with `FACT_VALUE`
(`fact_statement.py`), which is English only: `my`, `our`, `his`, `her` or `their`, the fact
words, `is` or `are`, the value. So neither a bare statement nor a request to remember in French,
German, Spanish or Romanian gets the old value note, although `forget_unrequested` refuses the
forget tool on the requests `asks_kept_fact_other` reads. Run on 2026-11-15 with no model, each
beside a row stating the same fact with `4826` in the same language:

| Message | Old value note |
| --- | --- |
| `Mon code d'alarme est 5528.` | none |
| `Retiens que mon code d'alarme est 5528.` | none |
| `Merk dir, dass mein Alarmcode 5528 ist.` | none |
| `Recuerda que mi código de alarma es 5528.` | none |
| `Reține că codul meu de alarmă este 5528.` | none |

The person ends up with both values stored and no word about the older one. The English reader
cannot be reused as it is: German puts the copula last after `dass`, Romanian puts the possessive
after the noun (`codul meu`), and a French or Spanish fact has an article or `de` between its
words.

## What to do

1. Write a pattern for each language with the same three groups as `FACT_VALUE` (possessive, fact
   words, value), and tests first: each message above names `4826`; a negated statement, another
   fact, another possessive and a repeated value name nothing.
2. Read the stored row in the language of the message, and read the fact after the request from
   `asks_kept_fact_other` rather than a new word list.
3. Replay every string literal of the brain's tests and every backticked string of
   `docs/readings/` through both builds, and Italian, Portuguese, Dutch and Polish statements,
   which must name nothing. A note only shows, so show none when unsure.

## History

- 2026-11-15: filed when the English requests to store or remember got the note (task 1198).
