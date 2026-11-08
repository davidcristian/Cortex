# One name or abbreviation picks another note language

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0076](../../adr/ADR-0076-closing-note-language.md)
**Verified:** 2026-11-08

`message_language` in `note_language.py` counts the words of each language's list in the person's
message and picks the one leader, else English. A short English request that names a place or an
abbreviation holding one function word of another language, and none of the English list, gets a
closing note in that language. Unit probes on 2026-11-08 against `0d6efa10e`:

| Message | Picked |
| --- | --- |
| `EU meeting Thursday 3pm, set reminder` | `ro` (`eu`) |
| `Reminder Sunday 10:00, water plants so they don't die` | `de` (`die`) |
| `Reminder: call Bob 9 EST Monday` | `fr` (`est`) |
| `Reminder Sunday 9:00: flight Las Vegas` | `es` (`las`) |
| `Alarm Friday 18:00 Le Bernardin` | `fr` (`le`) |

The same messages written with `9am` or `10am` pick English only because the reader splits `am`
out of the figure and counts it as the English `am`. A note in a language other than the reply's
is the defect.

## What to do

1. Decide the rule before the word list: a candidate is not to count a capitalized word that does
   not open a sentence, nor a word in capitals (names and abbreviations), and to add English words
   no other list holds (`they`, `don`, `set`, `reminder`, `alarm`, `meeting`), so a tie keeps
   English. Check that a German message still counts its lowercase `die` and `der`.
2. Stop reading `am` out of a clock figure, then replay every recorded draw message through the
   old and new picker.

## History

- 2026-11-08: filed by the audit of tonight's reader changes, from unit probes.
