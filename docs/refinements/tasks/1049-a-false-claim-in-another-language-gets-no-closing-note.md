# A false claim in another language gets no closing note

**Status:** open, actionable
**Area:** cross-cutting
**Origin:** [ADR-0074](../../adr/ADR-0074-replayed-tool-runs.md)
**Verified:** 2026-11-08

Seven readers that decide a closing note read the reply in English only, and each adds its note
when it finds a claim, so a false claim in French, German, Spanish or Romanian gets no note:
`claims_scheduled` (`UNSCHEDULED_CLAIM_NOTE`), `claims_yearly` (`MONTHLY_STORED_NOTE`),
`claims_kept` (`UNKEPT_CLAIM_NOTE`, when the message is not one `asks_kept` reads),
`claims_forgotten` (`UNFORGOTTEN_CLAIM_NOTE`), `says_not_stored` (`DELETED_UNFOUND_NOTE`),
`claims_folders` (`UNREAD_FOLDERS_NOTE`) and the searched-files claim (`UNSEARCHED_FILES_NOTE`).
The table is in the [readings](../../readings/closing-note-language.md#the-notes-and-their-readers-2026-11-08).
A recorded case: a French turn made only a `list_scheduled` call and replied `D'accord, j'ai bien
noté votre rappel [...] à 17h30.` with no note
([readings](../../readings/schedule-one-time-in-other-languages.md#results)).

## What to do

1. Start with `claims_scheduled` and `claims_kept`, the two whose notes showed most. Write near
   misses first (the same verb in a question, a condition or a negation), then read the four
   languages' forms; the safe direction is that the note shows.
2. Replay every recorded reply through the old and new reader, with counts, before shipping.

## History

- 2026-11-08: filed from step 1 of R-999, the table of every closing note and its reader.
