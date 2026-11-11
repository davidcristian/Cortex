# A false claim in another language gets no closing note

**Status:** done 2026-11-11
**Area:** cross-cutting
**Origin:** [ADR-0074](../../adr/ADR-0074-replayed-tool-runs.md)

Two readers that decide a closing note read the reply in English only, and each adds its note
when it finds a claim, so a false claim in French, German, Spanish or Romanian gets no note:
`claims_folders` (`UNREAD_FOLDERS_NOTE`) and the searched-files claim (`UNSEARCHED_FILES_NOTE`). Each of those notes is now written in the
person's language. The table is in the
[readings](../../readings/closing-note-language.md#the-notes-and-their-readers-2026-11-11).

## What to do

1. Start with `claims_folders`. Copy the shape of `claims_yearly_other`
   (`schedule_yearly_other.py`), a separate reader beside the English one. Write near misses first
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
- 2026-11-10: the `claims_scheduled` part done, five readers left open. `claims_scheduled_other`
  in `schedule_claim_other.py` reads a schedule claim in the four languages beside the English
  reader, so `UNSCHEDULED_CLAIM_NOTE` shows on the recorded French case; the note stays English.
  The replay moved 65 claims to 79 and lost none
  ([readings](../../readings/claim-readers-in-other-languages.md#a-schedule-claim-in-four-other-languages-2026-11-10)).
- 2026-11-10: the `claims_forgotten` part done, four readers left open (`claims_yearly`,
  `says_not_stored`, `claims_folders`, the searched-files claim). `claims_forgotten_other` in
  `forget_claim_other.py` reads a forget claim in the four languages beside the English reader;
  the replay moved 143 claims to 171 and lost none
  ([readings](../../readings/claim-readers-in-other-languages.md#a-forget-claim-in-four-other-languages-2026-11-10)).
- 2026-11-11: the `says_not_stored` part done, three readers left open (`claims_yearly`,
  `claims_folders`, the searched-files claim). `says_not_stored_other` in
  `forget_unfound_other.py` reads a not-stored claim in the four languages beside the English
  reader, so `DELETED_UNFOUND_NOTE`, now in the person's language, shows; the replay moved 128
  claims to 130 and lost none
  ([readings](../../readings/claim-readers-in-other-languages.md#a-not-stored-claim-in-four-other-languages-2026-11-11)).
- 2026-11-11: the `claims_yearly` part done, two readers left open (`claims_folders`, the
  searched-files claim). `claims_yearly_other` in `schedule_yearly_other.py` reads a yearly claim
  in the four languages beside the English reader; the replay moved 79 claims to 82, all three
  added being recorded messages, and lost none
  ([readings](../../readings/claim-readers-in-other-languages.md#a-yearly-claim-in-four-other-languages-2026-11-11)).
- 2026-11-11: done, the last two readers. `claims_folders_other` (`file_claim_other.py`) and
  `asks_files_other` (`file_request.py`) read a folder claim and a file question in the four
  languages, so `UNREAD_FOLDERS_NOTE` shows, and `access_claim_other.py` reads a no-access or
  not-found claim, so `UNSEARCHED_FILES_NOTE` shows; the replay lost no claim
  ([readings](../../readings/claim-readers-in-other-languages.md#a-folder-claim-and-a-no-access-claim-in-four-other-languages-2026-11-11)).
