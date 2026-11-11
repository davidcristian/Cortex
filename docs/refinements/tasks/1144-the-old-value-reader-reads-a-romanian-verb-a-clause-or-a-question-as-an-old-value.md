# The old value reader reads a Romanian verb, a clause or a question as an old value

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-11

`corrected_values` (`memory_old_value.py`) reads up to four words after a comma and `not`, `pas`,
`nicht`, `no` or `nu` as an old value. Called in the brain venv on 2026-11-11, after a route, a
range, a clock time and an English `no problem` were fixed the same night, it still returns:

| Message | Value |
| --- | --- |
| `Da, nu știu.` | `știu` |
| `I moved last year, not because I wanted to.` | `because I wanted to` |
| `Is my code 4862, not 4826?` | `4826` |

A row must hold the value whole and the reply must say it noted or changed something before
`old_value_note` shows, so each needs a row holding that text. The first two name a verb or a
clause rather than a value; the third is a question, which corrects nothing. A note that shows
when unneeded names a value as outdated and asks the person to forget it in a message of its own.

## What to do

1. Write the rows above as near misses beside corrections of the same form (`Este 4417, nu 4471.`,
   `It is 4862, not 4826.`).
2. Prefer a shape over a word list: skip a sentence ending in `?`, and decide whether a value after
   `nu` or Spanish `no` must be a number, a capitalized word or a word the row writes beside the
   new value.
3. Replay the readings and the proxy log through the old and new reader.

## History

- 2026-11-11: filed by the second audit of the night; reproduced with a unit call.
