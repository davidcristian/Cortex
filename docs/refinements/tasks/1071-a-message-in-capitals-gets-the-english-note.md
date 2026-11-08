# A message in capitals gets the English note

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0076](../../adr/ADR-0076-closing-note-language.md)
**Verified:** 2026-11-08

`message_language` in `note_language.py` skips every word written in capitals, so that `EU` and
`EST` name no language. A message written wholly in capitals then has no word left to count. Unit
probes on 2026-11-08: `RAPPELLE-MOI DEMAIN`, `ERINNERE MICH MORGEN UM 9 UHR`, `RECUÉRDAME MAÑANA`
and `AMINTEȘTE-MI MÂINE` each picked their own language before names were skipped and pick `en`
now. Counting capitals again in such a message brings back the abbreviation case:
`CALL BOB 9 EST MONDAY` picked `fr` before and `en` now. The English note is the safe side of
ADR-0076, and no recorded draw message is written in capitals
([the readings](../../readings/closing-note-language.md)).

## What to do

1. Write the four messages above and `CALL BOB 9 EST MONDAY` as tests first.
2. Count capitals in a message that has no lowercase letter only when two or more of its words
   are in one language's list, so that one `EST` or `EU` still names nothing, then replay every
   recorded draw message through the old and new picker.

## History

- 2026-11-08: filed when German nouns beside a capitalized word were made to count again, from unit
  probes of messages written in capitals.
