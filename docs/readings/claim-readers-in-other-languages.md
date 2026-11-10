# Readings: claim readers in other languages

Each closing note reader below reads a claim in French, German, Spanish and Romanian beside its
English reader, so the note shows when the claim is false. The table of every note and its reader
is in [the closing note readings](closing-note-language.md#the-notes-and-their-readers-2026-11-08).

## A schedule claim in four other languages, 2026-11-10

`claims_scheduled_other` (`schedule_claim_other.py`) reads a schedule claim in French, German,
Spanish and Romanian, and `unscheduled_claim` reads it beside `claims_scheduled`, so
`UNSCHEDULED_CLAIM_NOTE` shows on such a reply when no scheduling call succeeded. `j'ai programmé`,
`c'est programmé`, `he programado`, `queda programado` and `am programat` claim alone. A set,
created, added, noted or saved form (`j'ai bien noté`, `ist gespeichert`, `ich habe [...]
eingestellt`, `queda configurado`, `am setat`) claims only in a sentence naming a reminder, an
alarm, a timer or a task. As in English, a future form (`Je vous rappellerai`, `Ich erinnere
dich`, `Te lo recordaré`, `Îți voi aminti`) and an offer do not count. The near misses were
written first in each language: a question, a condition, a negation, an offer, a noted address.
Every distinct readings string (29,652) was replayed through the old reader and the new pair: 65
claims became 79 and none was lost. The 14 added are the recorded French and Romanian replies
(`D'accord, j'ai bien noté votre rappel [...] à 17h30.`, the recorded case of a turn whose only
call was `list_scheduled`, `C'est fait, j'ai programmé un rappel [...]`, `Am programat un
întunecire [...]`, `le minuteur est réglé pour 2h`), prose lines quoting them, and three lines
holding the question `Ce am programat?` with a quote mark after its question mark. The note stays
English. Script `replay2.py` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/58410d85-0aa8-4ebe-9853-99c9c16a6905/scratchpad/slot10/`.

## A forget claim in four other languages, 2026-11-10

`claims_forgotten_other` (`forget_claim_other.py`) reads a forget claim in French, German,
Spanish and Romanian, and `unforgotten_claim` reads it beside `claims_forgotten`, so
`UNFORGOTTEN_CLAIM_NOTE` shows on such a reply when no forget call deleted a row. `j'ai oublié`,
`c'est oublié`, `ich habe [...] vergessen`, `he olvidado` and `am uitat` claim alone; a deletion
(`supprimé`, `gelöscht`, `borrado`, `șters`) claims only in a sentence naming memory, since a
reminder or a file is deleted in the same words. A question, a condition, a negated clause, an
offer and a forgetting to do something (`J'ai oublié de vous demander`, `Am uitat să te întreb`)
do not count; these near misses were written first. Every distinct readings string (29,681) was
replayed through the old reader and the new pair: 143 claims became 171 and none was lost. The 28
added are the recorded replies `C'est fait, j'ai oublié le code [...]`, `Ich habe das vergessen.`
and `Am uitat codul.`, and readings lines quoting them. The note stays English. Script
`replay3.py` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/58410d85-0aa8-4ebe-9853-99c9c16a6905/scratchpad/slot10/`.
