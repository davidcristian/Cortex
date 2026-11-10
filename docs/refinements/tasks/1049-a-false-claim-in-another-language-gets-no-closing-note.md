# A false claim in another language gets no closing note

**Status:** open, actionable
**Area:** cross-cutting
**Origin:** [ADR-0074](../../adr/ADR-0074-replayed-tool-runs.md)
**Verified:** 2026-11-10

Six readers that decide a closing note read the reply in English only, and each adds its note
when it finds a claim, so a false claim in French, German, Spanish or Romanian gets no note:
`claims_scheduled` (`UNSCHEDULED_CLAIM_NOTE`), `claims_yearly` (`MONTHLY_STORED_NOTE`),
`claims_forgotten` (`UNFORGOTTEN_CLAIM_NOTE`), `says_not_stored` (`DELETED_UNFOUND_NOTE`),
`claims_folders` (`UNREAD_FOLDERS_NOTE`) and the searched-files claim (`UNSEARCHED_FILES_NOTE`).
The table is in the [readings](../../readings/closing-note-language.md#the-notes-and-their-readers-2026-11-08).
A recorded case: a French turn made only a `list_scheduled` call and replied `D'accord, j'ai bien
noté votre rappel [...] à 17h30.` with no note
([readings](../../readings/schedule-one-time-in-other-languages.md#results)).

## What to do

1. Start with `claims_scheduled`, whose note showed most. Copy the shape of `claims_kept_other`
   (`memory_claim_other.py`), a separate reader beside the English one. Write near misses first
   (the same verb in a question, a condition or a negation), then read the four languages' forms;
   the safe direction is that the note shows.
2. Replay every recorded reply through the old and new reader, with counts, before shipping.

## History

- 2026-11-08: filed from step 1 of R-999, the table of every closing note and its reader.
- 2026-11-10: the `claims_kept` part done, the six other readers left open. `claims_kept_other`
  in `memory_claim_other.py` reads a keep claim in the four languages and `unkept_note_due` reads it
  beside the English reader, so `UNKEPT_CLAIM_NOTE` shows; the note stays English. The replay moved
  71 claims to 81 and lost none
  ([readings](../../readings/closing-note-language.md#a-keep-claim-in-four-other-languages-2026-11-10)).
