# A forget card lists another fact that shares a number with the forgotten one

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-07

The `forget_memories` card lists the rows that contain the call's text, then every other row that
holds a token of four or more digits from those rows beside a word of four or more letters from
the text (`_repeating` in `memory_forget_chosen.py`). A token of four digits is often not the value
the person asked to forget: a phone prefix, a year, a postcode or an amount is shared by rows about
other facts, and a word of the text such as `number`, `that` or `remember` is in most exchanges.
Unit reproductions against `InMemoryMemoryStore` and `GLOBAL_MEMORY_SCOPE`:

| Call text | Row the text matches | Other row the card also lists and the delete removes |
| --- | --- | --- |
| `my phone number` | my phone number is `0176 5550 1234` | Anna's number is `0176 9988 7766` |
| `that my passport expires` | my passport expires in March `2026` | my dentist appointment is on 14 November `2026` |
| `remember that my car` | the reply says `Noted on 7 November 2026` | your bike lock code for `2026` is 4512 |

The card writes the rows listed for a value exactly as it writes the rows the text matched, so
the person cannot tell which rows the tool added. Approving the card deletes all of them, with no
undo.

## What to do

1. Write the rows above as failing tests first, beside the existing repeat tests in
   `test_memory_forget_chosen.py`, and keep every one of those passing.
2. Narrow what counts as a repeat. Options to compare: require a row to hold every value token of
   the matched row, not one of them (Anna's number shares only the prefix); leave out a token that
   reads as a year; and take the word from the text only when it is not in the row's
   `User:`/`Assistant:` wording that every exchange has.
3. Mark a row listed for a value on the card, for example under a second heading that names the
   shared value, so the person sees why it is there.

## History

- 2026-11-07: filed by the audit of the card that lists rows repeating a value.
