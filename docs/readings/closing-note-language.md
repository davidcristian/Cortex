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
