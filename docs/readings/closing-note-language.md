# Readings: the language of the notes the brain appends

Which notes `limit_notes` (`brain/packages/core/src/cortex_core/closing_notes.py`) can append to a
reply, which reader decides each one, what a reply form that reader misses in French, German,
Spanish or Romanian does, and how the note's own language is picked. The decision is
[ADR-0076](../adr/ADR-0076-closing-note-language.md).

## The notes and their readers, 2026-11-08

Read from the code at `00785a16e` plus the chat-only reader of the commit after it. "Adds" means a
missed form shows a note the reply did not need, the safe side; "drops" means a false claim in
another language gets no note, the defect.

| Note | Due when | Reader languages | A missed form |
| --- | --- | --- | --- |
| `REPLY_CAPPED_NOTE` | the reply hit its token cap | no text reader | none |
| `ROUNDS_SPENT_NOTE` | the turn spent its tool rounds | no text reader | none |
| `REPEATED_LINE_NOTE` | the repeat watch ended the reply | no text reader | none |
| `UNSCHEDULED_CLAIM_NOTE` | `claims_scheduled` and no scheduling call succeeded | English | drops |
| `MONTHLY_STORED_NOTE` | a monthly store and `claims_yearly` | English | drops |
| `STORED_TIME_NOTE` | a stored time and not `names_time_of_day` | English, French `17h30`, German `Uhr`, Spanish `a las` | adds |
| `DAILY_STORED_NOTE` | a daily store and not `names_repeat` | five | adds |
| `ONCE_STORED_NOTE` | a one-time store after a refused weekly call | no text reader | none |
| `UNKEPT_CLAIM_NOTE` | memory withheld and `claims_kept`, or `asks_kept` of the message | reply English, message five | drops when the message is not read |
| `KEPT_BEYOND_CHAT_NOTE` | a shared store and `claims_chat_only` | five | drops |
| `UNFORGOTTEN_CLAIM_NOTE` | `claims_forgotten` and nothing deleted, or a refused forget and not `claims_kept` or `names_removal` | English | drops, except the refused branch's `claims_kept`, which adds |
| `NUMBERS_LEFT_NOTE` | numbers left and `says_forgotten` | five | drops |
| `DELETED_UNFOUND_NOTE` | a delete, an unmatched call and `says_not_stored` | English | drops |
| `DECLINED_FORGET_NOTE` | a denied forget card and not `names_still_held` | reply English, note five | adds |
| `UNREAD_FOLDERS_NOTE` | `claims_folders` on an untainted file question | English | drops |
| `UNSEARCHED_FILES_NOTE` | a claim of searched files with no file call | English | drops |

The seven readers that read the reply in English and drop a note are one task, R-1049.

## How often each note shows

Over every turn record of the last two nights' scratchpads (749 distinct replies, 189 in the four
languages by a word count over message and reply), counting the brain's English note text:

| Note | All replies | Under a reply in another language |
| --- | --- | --- |
| `UNKEPT_CLAIM_NOTE` | 66 | 0 |
| `UNFORGOTTEN_CLAIM_NOTE` | 24 | 0 |
| `ONCE_STORED_NOTE` | 9 | 0 |
| `DAILY_STORED_NOTE` | 8 | 7 |
| `STORED_TIME_NOTE` | 8 | 7 |
| `NUMBERS_LEFT_NOTE` | 4 | 3 |
| `DELETED_UNFOUND_NOTE` | 4 | 0 |
| `UNSCHEDULED_CLAIM_NOTE` | 3 | 0 |

The overall counts follow what each night's slots drew. The two notes shown most under a reply in
another language, `DAILY_STORED_NOTE` and `STORED_TIME_NOTE`, are the two the decision is built
for first, and `NUMBERS_LEFT_NOTE`, the third, after them.

## A note the model restates

Five draws of 2026-11-08
(`/tmp/claude-1000/-home-david-Files-Git-Cortex/5e7bbbe2-0692-4951-9718-a5c1c4b48de9/scratchpad/slot10/draws-cand.jsonl`,
chats `s10-cand-*`) wrote the
`DAILY_NOTE` a scheduling result ends with into the reply in the reply's language. All five
changed "Ask to make it one time" into a promise ("dímelo y lo ajustaré", "je ferai le
nécessaire"), and the Romanian one has two words that are not Romanian (`uninel`, `Acestinel`).

## The language pick: rows and pass rule, written before the replay

Rows: every one of the 749 recorded messages, read by `message_language`, against the language
the same word lists read in its reply (cut at the first appended note). Every disagreement is
read by eye.

- The pick **passes** when no message is given a language other than its reply's, among replies
  in one of the five languages. A pick of English under a reply in another language is today's
  behaviour and is counted, not failed.
- On a fail, the note stays English and the word lists are corrected in the next slot.

## The language pick: results, 2026-11-08

`message_language` at the commit that adds it, over the 749 messages; the reply column is the same
word lists read on the reply.

| Reply read as | Picked the same | Picked English | Picked another language |
| --- | --- | --- | --- |
| French, 110 | 107 | 3 | 0 |
| German, 53 | 50 | 3 | 0 |
| Spanish, 20 | 19 | 1 | 0 |
| Romanian, 25 | 23 | 2 | 0 |
| English, 541 | 536 | none | 5 |

Read by eye, the five English rows are Spanish or Romanian replies too short for the lists
("Entendido, lo recordaré.", "Am uitat codul.") and the pick is right on all five. Of the nine
English picks under another language, six are English messages the model answered in French,
German or Romanian, and three are short messages that tie ("Was ist geplant?", "Ce am programat?")
or match no list ("No guardes rencor, mi jefe se llama Luis."). No message got a language other
than its reply's, so the pick **passes**.

## Live turns on the shared stack, 2026-11-08

The `cortexn16` stack brain rebuilt from the commit that adds the pick, one new chat per message,
cards approved (`/tmp/claude-1000/-home-david-Files-Git-Cortex/5e7bbbe2-0692-4951-9718-a5c1c4b48de9/scratchpad/slot12/draws.jsonl`).
Each turn made one successful `schedule_task` call stored at 09:00; the SM clock read 0.56 to
0.57 of its maximum.

| Message | Reply names a time | Note shown |
| --- | --- | --- |
| `Rappelle-moi le 14 décembre d'envoyer le colis.` | no | French |
| `Erinnere mich am 14. Dezember an das Paket.` | no | German |
| `Recuérdame cada año el 12 de octubre el cumpleaños de Ana.` | `a las 09:00` | none |
| `Amintește-mi pe 14 decembrie să trimit coletul.` | `la ora 09:00` | none |

## The pick without letters: replay, 2026-11-08

A name's letters picked the note's language under an English message (`Lunch with Jürgen Müller
and Björn on Friday.` read German), so the pick now reads only the word lists and the Spanish
marks ¿ and ¡, and the Spanish list adds `guarda` and `guardes`. The rule of the first
replay applies unchanged. Over the same 749 messages, with each reply read by the earlier pick:

| Reply read as | Picked the same | Picked English | Picked another language |
| --- | --- | --- | --- |
| French, 110 | 107 | 3 | 0 |
| German, 53 | 50 | 3 | 0 |
| Spanish, 20 | 20 | 0 | 0 |
| Romanian, 25 | 23 | 2 | 0 |
| English, 541 | 536 | none | 5 |

One pick changed: `No guardes rencor, mi jefe se llama Luis.` moved from English to Spanish under
a Spanish reply. The five English rows are the same five read by eye above, so the pick
**passes**. Replay `replay3.py` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/5e7bbbe2-0692-4951-9718-a5c1c4b48de9/scratchpad/slot15/`.

## Live rows on the pick without letters, written before the draws, 2026-11-08

The stack brain rebuilt from the commit that rewords the three schedule notes, one new chat per
message, cards approved. This measures the shipped notes and changes nothing; a wrong-language
note is filed as a task with its reproduction.

| Row | Message | Passes when |
| --- | --- | --- |
| L1 | `Remind me to have lunch with Jürgen Müller and Björn on Friday.` | every note shown is English |
| L2 | `Recuérdame el viernes llamar a Begoña.` | every note shown is Spanish |
| L3 | `Remind me Tuesday at 8 to stretch, keep it going.` | a one day note opens "(A reminder" |

**Results.** Stack brain image `ac39ab37b84e`, draws at 08:34 (chats `s15-a` to `s15-c`), SM
clock 0.53 to 0.57 of `clocks.max.sm`. L1 stored Friday 12:00 and the reply named it, so no note
was due. L2 stored Friday 09:00, the reply named no time, and the note was the Spanish "(Un
recordatorio creado o cambiado aquí es a las 09:00. ...)". In L3 the weekly call was refused and
the retry kept the repeat as `every_seconds` 604800, so no one day note was due and none showed.
No note was in a wrong language, so the rows pass. Log `draws.log`, records `draws.jsonl` and
items `items.tsv` in the slot directory of the replay above; every item and row was deleted.

## Names and abbreviations

On 2026-11-08 unit probes found five short English requests whose note language came from one
name or abbreviation: `EU` read as Romanian, `EST` and `Le Bernardin` as French, `Las Vegas` as
Spanish, and `die` in `so they don't die` as German. `message_language` now skips a word in
capitals and a capitalized word beside another one inside a sentence, and the English list holds
`they`, `don`, `set`, `reminder`, `alarm` and `meeting`. Replayed through the old and new picker,
223 distinct turn log messages changed once (`EU meeting Thursday 15:00, set reminder.`, Romanian
to English) and 1,810 backticked strings of `docs/readings/` changed none. Script
`/tmp/claude-1000/-home-david-Files-Git-Cortex/5e7bbbe2-0692-4951-9718-a5c1c4b48de9/scratchpad/slot19/replay3.py`.

German capitalizes every noun, so that skip also dropped `Uhr`, `Morgen` and the polite `Sie`
beside a noun: `Termin Montag 9 Uhr` and `Rufen Sie Herrn Weber an` got the English note. Those
three words now count beside a capitalized word, while a German article inside a name
(`Watch Die Hard Friday`) stays skipped. Replayed against the picker before this change, 223 turn
log messages and 1,814 readings strings changed none, and four German probes moved from English to
German. Script
`/tmp/claude-1000/-home-david-Files-Git-Cortex/5e7bbbe2-0692-4951-9718-a5c1c4b48de9/scratchpad/slot20/replay.py`.

## Messages in capitals, 2026-11-10

Skipping every word in capitals left a message written wholly in capitals with no word to count,
so `RAPPELLE-MOI DEMAIN`, `ERINNERE MICH MORGEN UM 9 UHR`, `RECUÉRDAME MAÑANA` and
`AMINTEȘTE-MI MÂINE` got the English note. Counting those words again whenever two are in one
list, the first remedy written down, moves abbreviations off English: `CALL BOB MON 9 EST` reads
as French and `FLIGHT LOS ANGELES TO LAS VEGAS` as Spanish. A message with no lowercase letter now
counts only its words of four letters or more, and only when two of them are in one language's
list; the shorter words stay abbreviations. Near misses that stay English are in
`test_note_language.py`: one long word (`TAKE CARE`, `DO ME A FAVOR: BOOK LAS VEGAS`) and short
words only (`CALL BOB 9 EST MONDAY`, `REMIND ME TO CALL MON 9 EST`). Replayed through the old and
new picker, 29,065 distinct strings of `docs/readings/` (785 with no lowercase letter) and the 46
distinct driver messages still on disk changed none. A forget in capitals with two German list
words (`VERGISS BITTE DEN TÜRCODE 7319, ALLES ANDERE BLEIBT.`) now reads as German, so its `DEN`
no longer names the den row; with one (`VERGISS DEN TÜRCODE 7319, ...`) it still reads as English,
and the forget reader adds a German reading by its forget verb
([forget-keep-clause.md](forget-keep-clause.md)). Scripts `replay1071.py`, `probe2.py` and log `replay1071.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/58410d85-0aa8-4ebe-9853-99c9c16a6905/scratchpad/slot1/`.

## A keep claim in four other languages, 2026-11-10

`claims_kept_other` (`memory_claim_other.py`) reads a keep claim in French, German, Spanish and
Romanian: `c'est noté`, `j'ai bien noté`, `je m'en souviendrai`, `ich habe mir das gemerkt`, `das
ist gespeichert`, `lo recordaré`, `queda anotado`, `am reținut`, `voi ține minte`, and an opening
`Noté`, `Notiert`, `Anotado` or `Notat` on the reply's first line. A question, a claim after a
condition word (`si`, `wenn`, `falls`, `cuando`, `dacă`) and a claim whose clause holds a negation
claim nothing, and a negation in another clause (`Pas de souci, c'est noté.`) does not count.
`unkept_note_due` reads it beside `claims_kept`, so `UNKEPT_CLAIM_NOTE` shows on such a reply on a
turn that stores nothing; `claims_kept` itself is unchanged, so the refused forget branch of
`UNFORGOTTEN_CLAIM_NOTE` reads English only. The near misses were written first:
the same verbs in a question, a condition and a negation in each language, plus `Ich merke mir
Namen schlecht.` and English `Note my code 7319.`. Every distinct readings string (29,123) was
replayed through the old reader (`claims_kept`) and the new one (either reader): 71 claims became
81, none was lost, and the 10 added are the recorded French, German and Spanish replies
(`D'accord, j'ai bien noté votre rappel [...]`, `Je m'en souviendrai pour la suite de notre
conversation`, `C'est noté, je retiens [...]`, `Notiert.`, `Entendido, lo recordaré.`) written in
several lines, and one prose fragment. No English string was added. The note stays English under
such a reply: `UNKEPT_CLAIM_NOTE` has no translations, and a wording in another language is a pick.
Script `replay1049.py` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/58410d85-0aa8-4ebe-9853-99c9c16a6905/scratchpad/slot2/`.

## A keep claim naming a row still stored, 2026-11-10

`unkept_note_due` skips `UNKEPT_CLAIM_NOTE` when every keep claim of the reply names only a row
still stored. Two forms got the note anyway. A reply in Spanish or Romanian saying the row a keep
clause spared stayed (`He borrado tu PIN del banco y he guardado tu código del gimnasio.`) had no
exception, and `OK. I've forgotten your phone number and kept Anna's.` (flow k of
[the short groups readings](forget-value-short-groups.md)) named a row no forget call matched, so
`TaintLedger.forget_spared` did not hold it. The forget card now adds the rows the message's keep
clause names (`keep_named`, `forget_keep_named.py`), and `names_spared_other` reads a claim of
`claims_kept_other` whose verb keeps or saves (`guardado`, `salvat`, `gespeichert`, `enregistré`),
taking the words of its clause. Each object word must now be a word of such a row (it was one
shared word), so `kept your new phone number` beside Anna's row keeps the note. A noted verb, an
opening `Guardado.`, a new value, and a row stored in another language than the reply keep it too.

Every distinct readings string (29,621) was replayed through the old and new `unkept_note_due`
with six spared sets (none, Anna's row, the shed, gym rows in English, Spanish and Romanian), each
with and without a forget call. Two results changed, both a readings line quoting the Anna reply
with more words after it, and both now show the note. No recorded reply in another language keeps
a stored row (`names_spared_other` holds on 0 strings). Script `replay.py` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/58410d85-0aa8-4ebe-9853-99c9c16a6905/scratchpad/slot10/`.

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
