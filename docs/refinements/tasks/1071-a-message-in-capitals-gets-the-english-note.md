# A message in capitals gets the English note

**Status:** done 2026-11-10
**Area:** memory
**Origin:** [ADR-0076](../../adr/ADR-0076-closing-note-language.md)

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
- 2026-11-09: the forget reader now drops the function words of the language `message_language`
  picks, so a forget in capitals keeps German `DEN` as a fact word. A unit call of `unnamed` on
  `VERGISS DEN TÜRCODE 7319, ALLES ANDERE BLEIBT.` lists the row `the den alarm code is 7319`
  beside the door row, a row the person asked to keep (`probe2.py` in
  `/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot18/`).
- 2026-11-10: done. The remedy above moved abbreviations off English (`CALL BOB MON 9 EST` read as
  French), so a message with no lowercase letter now counts only its words of four letters or
  more, when two are in one language's list. The four messages read as their own language, nine
  near misses stay English, and the replay changed no recorded string
  ([the readings](../../readings/closing-note-language.md)). A forget in capitals with one German
  list word still reads as English: task 1108.
