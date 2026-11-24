# A new value of a fact stated in another language names no old value

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-24

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
   fact, another possessive and a repeated value name nothing. German needs both orders, and after
   `dass` only a value opening with a digit separates the fact words from the value. In Romanian
   the fact words are the noun before the possessive and the words after it, so the row search
   takes a run of them that the row holds whole (`alarmă`), since `find_value` matches one text.
2. Read the stored row in the language of the message. `asks_kept_fact_other` returns only a
   bool: split it so one function returns the fact text after the request and the bool tests it.
3. Reuse what is there: `NOT` already holds `pas`, `nicht`, `no`, `nu`, `nunca` and `jamais`,
   `asks_not_kept` reads the four languages, and the value rule (first word with a digit or a
   capital, the same other words in both values) applies as it is. `now`, `actually` and `new`
   are read in English only, so `maintenant 5528` and `nouveau code` name nothing until a reading
   of each is written.
4. Replay with the scripts in `~/.cache/cortex-run/2026-11-24/f2/`, adding synthetic rows built in
   each language, and Italian, Portuguese, Dutch and Polish statements, which must name nothing. A
   note only shows, so show none when unsure.

## History

- 2026-11-15: filed when the English requests to store or remember got the note (task 1198).
- 2026-11-24: checked again after the old value reader began to read only a statement's first
  sentence: the five messages above still name nothing. The steps now name what exists to reuse
  and what the German and Romanian orders need. Left open, since a note not shown is the safe
  direction.
