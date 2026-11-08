# Readings: corrections and follow-ups

What the brain does with the message a person sends right after a turn to change what it did: the
follow-up a closing note invites, and a plain correction ("no, I meant Wednesday", "undo that",
"cancel the last one", "forget what I just told you", "my number is X, not Y"). A flow passes when
the follow-up changes the item or row the first turn made, adds no second copy, and the reply says
what happened. Closing notes are [ADR-0076](../adr/ADR-0076-closing-note-language.md), scheduling
[ADR-0025](../adr/ADR-0025-scheduling-reminders.md), memory [ADR-0008](../adr/ADR-0008-memory-v1.md).

## The rig

**2026-11-08**, the `cortexn16` GPU stack with the brain built from `19e115765`: the resident
cortex (gemma-4-12B) at a context of 16,384 tokens, no deep tier and escalation off, memory on
pgvector with the default `global` scope, schedules on Redis in `Europe/Berlin`, the brain's clock
on Sunday 8 November in the morning. Turns ran over `Converse` from the host driver with every card
approved, each chat named `s16-<flow>`, every turn of a flow in the same chat unless the row names
another. After every turn the driver read the chat's `cortex:schedule:*` records and the chat's
`memories` rows; after each flow it cancelled the flow's items and deleted its rows. Run logs and
records: `flows1.log`, `flows2.log`, `pass1.jsonl`, `pass2.jsonl` and the `*-items.tsv` files in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/5e7bbbe2-0692-4951-9718-a5c1c4b48de9/scratchpad/slot16/`.

## 1. The follow-ups the closing notes invite

Rows written before the first draw. Each first turn is one that earlier draws showed provoking the
note; the follow-up is sent whether or not the note came, and the result says which.

| Flow | First turn | Note it should provoke | Follow-up | Pass when |
| --- | --- | --- | --- | --- |
| t1 | `Remind me on 14 December to send the parcel.` | stored time | `Change it to 3 in the afternoon.` | one item, 14 Dec 15:00 |
| t2 | `Rappelle-moi le 14 décembre d'envoyer le colis.` | stored time, French | `Mets-le plutôt à 15 h.` | one item, 14 Dec 15:00 |
| d1 | `Remind me at 17:30 to call the plumber.` | daily | `Make it one time.` | one one-time item, 8 Nov 17:30 |
| d2 | `Erinnere mich um 17:30 Uhr an die Wäsche.` | daily, German | `Mach sie einmalig.` | one one-time item, 8 Nov 17:30 |
| w1 | `Remind me at 6pm to put the bins out for Monday's collection.` | weekday | `Move it to Monday.` | one item, 9 Nov 18:00 |
| w2 | `Recuérdame a las 18 sacar la basura para la recogida del lunes.` | weekday, Spanish | `Muévelo al lunes.` | one item, 9 Nov 18:00 |
| o1 | `Rappelle-moi mardi à 8 h de m'étirer, tout le temps.` | one day after a weekly refusal | `Fais-le chaque semaine.` | one weekly rule, Tuesday 08:00 |
| n1 | seeds `Remember that my gym locker number is 5521.` and `Remember that the shed padlock code is also 5521.` in two chats, then `Forget my gym locker number.` | numbers left | `Forget the number itself.` | no row holds 5521 |
| u1 | seed `Remember that my phone number is 0612345678.`, then `Note that my phone number is now 0699000000, and delete the old one.` | not stored | `Remember that my phone number is 0699000000.` | a row holds 0699000000 |
| c1 | `My seat on the train is 14C, keep it in mind while we talk.` | chat only | `Then forget it.` | no row holds 14C |
| c2 | `Ma place dans le train est la 14C, garde-la en tête pendant notre conversation.` | chat only, French | `Alors oublie-la.` | no row holds 14C |

In every flow the reply to the follow-up must also be true of the store after it.

**Result.** Turns from 08:41 to 08:50, SM clock 0.52 to 0.69 of `clocks.max.sm`. Arguments are
from the brain's `tool.invocation` log lines.

| Flow | Note shown | Follow-up calls | Store after | Reply | Pass |
| --- | --- | --- | --- | --- | --- |
| t1 | yes, 09:00 | `edit_scheduled` `at_time` 15:00 | a daily rule from 8 Nov 15:00 | "3:00 PM on 14 December" | no, R-1058 |
| t2 | no, the reply named `9h00` | `edit_scheduled` `at_time` 15:00 | a daily rule from 8 Nov 15:00 | "le 14 décembre à 15h00" | no, R-1058 |
| d1 | no, a one-time `at` was stored | `schedule_task` again, same `at` | one one-time item, no copy added | "set as a one-time event" | yes |
| d2 | yes, German | `edit_scheduled` `every_seconds` 0 | one one-time item, 8 Nov 17:30 | "nur einmalig" | yes |
| w1 | yes, Sunday 2026-11-08 | `cancel_scheduled` (card), `schedule_task` | one item, 9 Nov 18:00 | "6:00 PM tomorrow, Monday" | yes |
| w2 | yes, Spanish | `cancel_scheduled` (card), `schedule_task` | one item, 9 Nov 18:00 | "lunes 9 de noviembre a las 18:00" | yes |
| o1 | no: the retry stored `every_seconds` 604800 | `list_scheduled` | one item every 7 days from 10 Nov 08:00 | "déjà configuré" | yes |
| n1 | no: the turn deleted the other holder itself | a forget that matched nothing | no row holds 5521 | "nothing for me to forget" | yes, R-1059 |
| u1 | yes | none, the exchange was stored | a row holds 0699000000 | "I've noted" | yes |
| c1 | no, see below | `forget_memories` `14C` (card) | no row holds 14C | "I've forgotten" | yes |
| c2 | yes, English (R-999) | `forget_memories` `14C` (card) | no row holds 14C | "j'ai oublié" | yes |

- **t1 and t2.** `edit_scheduled` has no argument for a one-time date and time, so `at_time` made
  each item a daily rule from today and dropped 14 December. Filed as
  [R-1058](../refinements/tasks/1058-moving-a-one-time-reminder-makes-it-repeat.md). The same slot
  made `daily_after` (`schedule_daily.py`) read an edit with `at_time` and no day selector as a
  daily store, so such a reply now ends with `DAILY_STORED_NOTE` unless it names the repeat.
- **n1.** In the first turn the model forgot `gym locker number`, read the result saying another
  row still held 5521, and forgot `5521` too, unasked; the second card listed the shed padlock
  exchange. Filed as
  [R-1059](../refinements/tasks/1059-a-forget-deletes-another-fact-that-shares-its-number-unasked.md).
- **c1.** The reply "I'll keep that in mind as we continue our conversation!" got no note,
  because `claims_chat_only` did not read `as we continue`. The same slot added `as we continue`
  and `as we go on with` before the conversation word, with near-miss replies as tests first. Of
  813 recorded replies in this run's and the previous night's driver records, only c1's reads
  differently through the new reader.
- **o1.** `tout le temps` did not stop the weekly refusal; the model then stored the repeat as a
  seven-day interval, which the refusal does not read, so the person got a weekly item.

## A correction typed while the reply streams, on the Linux shell

The shell on `Xvfb` against the same stack, `BodyService` listening on 23151 (`ss`), a new chat
(`ctrl+n`). `Remind me on Tuesday at 9 to call the dentist.` was sent, and four seconds later,
while the reply streamed, `No wait, I meant Wednesday.` was typed and Enter pressed. Frames
`mid-a.png` to `mid-e.png` in the slot directory above.

- During the turn Enter did not send: the composer kept the text and its button showed Stop. The
  first reply ended "OK. I've set a reminder to call the dentist on Tuesday, November 10th, at
  9:00 AM." and `ONCE_STORED_NOTE`, after a refused weekly call. The text was still in the
  composer, and a second Enter sent it.
- The correction called `edit_scheduled` with `at_time` 09:00 and `on_days` `["wed"]`, with no
  card. The reply said "It's now set for Wednesday, November 11th, at 9:00 AM.", but the item
  became a weekly rule every Wednesday: the weekly form of R-1058.

## 2. Plain corrections

Rows written before the first draw, on the same rig. x8 seeds the old value in its own chat first,
and its second turn asks in the correcting chat.

| Flow | First turn | Correction | Pass when |
| --- | --- | --- | --- |
| x1 | `Remind me on Tuesday at 9 to call mom.` | `No, I meant Wednesday.` | one item, 11 Nov 09:00 |
| x2 | `Rappelle-moi mardi à 9 h d'appeler maman.` | `Non, je voulais dire mercredi.` | one item, 11 Nov 09:00 |
| x3 | `Remind me tomorrow at 10 to water the plants.` | `Undo that.` | no item |
| x4 | `Recuérdame mañana a las 10 regar las plantas.` | `Deshaz eso.` | no item |
| x5 | `Remind me tomorrow at 11 to buy stamps. Also remind me tomorrow at 12 to pick up the dry cleaning.` | `Cancel the last one.` | only the 11:00 item |
| x6 | `My locker code at the pool is 7319.` | `Actually, forget what I just told you.` | no row holds 7319 |
| x7 | `Mein Fahrradschloss hat den Code 2468, merk dir das.` | `Vergiss bitte, was ich dir gerade gesagt habe.` | no row holds 2468 |
| x8 | seed `Remember that my bike lock code is 4826.` | `My bike lock code is 4862, not 4826.`, then `What is my bike lock code?` | the answer is 4862 |

**Result.** Turns from 08:49 to 08:55, SM clock 0.52 to 0.71 of `clocks.max.sm`, beside the shell
flow above.

| Flow | Correction calls | Store after | Reply | Pass |
| --- | --- | --- | --- | --- |
| x1 | `edit_scheduled` `at_time` 09:00, `on_days` `["wed"]` | a weekly rule, Wednesdays 09:00 | "set for Wednesday at 9:00 AM" | no, R-1058 |
| x2 | `cancel_scheduled` (card), `schedule_task` after a refused weekly call | one item, 11 Nov 09:00 | "prévu pour mercredi à 9 h" and `ONCE_STORED_NOTE` in English | yes |
| x3 | `cancel_scheduled` (card) | no item | "I've cancelled that reminder" | yes |
| x4 | `list_scheduled`, `cancel_scheduled` (card) | no item | "he cancelado el recordatorio" | yes |
| x5 | `list_scheduled`, `cancel_scheduled` on the 12:00 item (card) | only the 11:00 item | "cancelled the reminder to pick up the dry cleaning" | yes |
| x6 | `forget_memories` `7319` (card) | no row holds 7319 | "I've forgotten that information" | yes |
| x7 | `forget_memories` with a text no row holds | the 2468 row stays | "nicht dauerhaft gespeichert", nothing deleted | no, R-1061 |
| x8 | none | rows hold 4826 and 4862 | "I've updated that for you", then 4862 | no, R-1062 |

- **x7.** The forget text planned in the thinking was `Fahrradschloss Code 2468`, while the row
  reads `Fahrradschloss hat den Code 2468`, so `_NONE_FOUND` told the model to say nothing was
  stored. Filed as
  [R-1061](../refinements/tasks/1061-a-forget-of-what-was-just-said-can-match-nothing-and-say-it-was-never-stored.md),
  the no-value form of
  [R-969](../refinements/tasks/969-a-forget-of-the-old-value-can-match-nothing-and-say-none-is-stored.md).
- **x8.** The same chat answered 4862 from its own history, which passes the row as written, but
  the old row stayed and the reply said "updated". Filed as
  [R-1062](../refinements/tasks/1062-a-correction-of-a-stored-value-says-updated-and-keeps-the-old-row.md).
- **x2.** The French correction cancelled and stored anew; the English x1 and the shell flow edited
  the one-time item into a weekly rule. Two of three corrections of a day used the edit.

No flow needed the deep model: the stack runs no deep tier and escalation is off, so no correction
was tried across a handoff. After every flow the driver cancelled its items and deleted its rows;
at 08:55 `memories` held the three hello rows and Redis no schedule item.

## The daily note over an edit, on the fixed build

At 08:55 the stack brain was rebuilt from the tree holding the `daily_after` change, and t1 and x1
were drawn once more (chats `s16-v1`, `s16-v2`, log `flows3.log`). `Change it to 3 in the
afternoon.` again made a daily rule from 8 Nov 15:00; the reply said "3:00 PM on 14 December" and
now ended with `DAILY_STORED_NOTE`, which is true of the item. `No, I meant Wednesday.` this time
cancelled and stored a one-time item on 11 Nov 09:00, with `ONCE_STORED_NOTE` after a refused
weekly call. Both chats' items were cancelled and their rows deleted.

## Counts

Of 11 note follow-ups, 9 passed and 2 failed (R-1058, both time changes). The note came in 6 of 11
first turns; the other 5 had a reason the result row names. Of 8 corrections plus the shell flow, 5
passed and 4 failed (R-1058 twice, R-1061, R-1062). Every cancel, and every forget that matched a
row, showed its card; an edit shows none.
