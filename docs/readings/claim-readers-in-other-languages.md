# Readings: claim readers in other languages

Each closing note reader below reads a claim in French, German, Spanish and Romanian beside its
English reader, so the note shows when the claim is false. The table of every note and its reader
is in [the closing note readings](closing-note-language.md#the-notes-and-their-readers-2026-11-11).

## A schedule claim in four other languages, 2026-11-10

`claims_scheduled_other` (`schedule_claim_other.py`) reads a schedule claim in French, German,
Spanish and Romanian, and `unscheduled_claim` reads it beside `claims_scheduled`, so
`UNSCHEDULED_CLAIM_NOTE` shows on such a reply when no scheduling call succeeded. `j'ai programmé`,
`c'est programmé`, `he programado`, `queda programado` and `am programat` claim alone; in French
an object pronoun may stand before the auxiliary (`je vous ai programmé`) and up to two words
after it (`j'ai également programmé`). A set,
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

The French present counts too: `j'oublie`, `je l'oublie` and, beside memory, `je supprime` or
`j'efface`, outside a question, a condition and a negation, and never after `que` or in a sentence
telling a habit (`toujours`, `souvent`, `parfois`), so `J'oublie souvent mes clés.` and
`Voulez-vous que j'oublie ce point.` do not count; these near misses were written first. Of
30,424 distinct readings strings, claims went from 36 to 39, the 3 added the recorded m6 reply
`J'oublie ce que vous venez de mentionner` and lines quoting it, and none was lost; of 388
distinct draw replies, 8 became 9, the added one that reply. Scripts `replay2.py` and `replay3.py`
in the run's `slot20` scratch directory.

## A not-stored claim in four other languages, 2026-11-11

`says_not_stored_other` (`forget_unfound_other.py`) reads a not-stored claim in French, German,
Spanish and Romanian beside the English `says_not_stored`, so `DELETED_UNFOUND_NOTE` shows after
a delete and a forget that matched nothing. A clause counts when it holds a negation and a find or
store verb (`n'ai pas trouvé`, `nie gespeichert`, `no encontré`, `nu am găsit`) or a no-record
form (`aucune trace`, `keinen Eintrag`, `ningún registro`, `nicio înregistrare`). The near misses
were written first, each in the four languages: a question, a clause after a condition word, a
found and deleted fact, a delete that held (`n'est plus enregistré`, `nicht mehr gespeichert`,
`ya no está guardado`, `nu mai este salvat`, `il n'en reste aucune trace`) and a new fact not
kept (`Votre nouveau numéro n'a pas été enregistré`). French and Spanish keep verbs count only as
past participles, since the first replay read the idioms `Ne garde pas rancune` and `No guardes
rencor` as claims.

Every distinct readings string and line (23,300) and the 30 distinct replies in the shared
stack's proxy log were replayed through the old reader and the new one (either reader): 128
claims became 130, none was lost, and the proxy replies changed none. The two added are a
recorded German reply (`nicht dauerhaft gespeichert`, on a turn that deleted nothing, so no note
was due) and a prose line where an English `had no` and a Spanish `guardado` share a clause. Script
`/tmp/claude-1000/-home-david-Files-Git-Cortex/f3217b06-cdcf-4ffa-92c2-cc5df81e7d11/scratchpad/slot4/replay1049.py`,
log `replay1049.log` beside it.

