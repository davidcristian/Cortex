# Readings: words mentioned, not used

What a message does when it holds the words the brain's typed readers act on (remember, forget,
don't save, keep, delete, remind, every day, a weekday) without asking for that action: in a
quote, in a report of what someone else said, in a hypothetical or in a question. For each turn:
the rows stored and deleted against what the message asked, any forget card, the schedule items,
and whether every closing note was true. Scheduling is in
[ADR-0025](../adr/ADR-0025-scheduling-reminders.md), forgetting in
[ADR-0075](../adr/ADR-0075-forget-chosen-memories.md), the closing notes in
[closing-note-language.md](closing-note-language.md).

## The rig

**2026-11-10**, the `cortexn18` GPU stack at the tree of that night: the resident cortex
(gemma-4-12B) at a context of 16,384 tokens, memory on pgvector with the default `global` scope,
the filesystem sidecar, Redis schedules with `CORTEX_SCHEDULE_TZ=Europe/Berlin`. The turns ran on
Tuesday at 06:30 to 06:42 local time. A host driver sent each turn over `Converse` with every card
approved, one chat per turn (`s17-<flow>`), and two turns ran on the Linux shell
([body-overlay.md](../runbooks/body-overlay.md#the-tauri-app-on-linux-headless)) on `Xvfb`. Every
row and schedule item was deleted before each flow; a flow marked with a seed first stored
`Remember that my locker code is 4417.` in a chat of its own. SM clock 0.57 of `clocks.max.sm`.

## Turns

| Flow | Message | Calls | Stored | Notes | Result |
| --- | --- | --- | --- | --- | --- |
| m1 | My daughter keeps saying "don't forget my birthday", it's on March 3. Remember that. | `spawn_subagents` ran | 1 row | none | correct |
| m2 | The film was called "Remember Me". What year did it come out? | `search_files` failed, `spawn_subagents` | 0 rows | none | nothing to keep |
| m3 | My boss told me to delete the old files tomorrow. Remind me at 10 to ask him which ones. | `schedule_task` `at` tomorrow 10:00 | 1 row, 1 item | none | the day came from the reported clause; the reply said tomorrow |
| m4 | If I said "forget my locker code", would you delete it? (seed) | none | seed kept, 1 row | none | correct |
| m7 | Do you still have my locker code, or did I ask you to forget it? (after m4) | none | seed kept | none | correct, named 4417 |
| m5 | Anna said: "remind me every day at 8 to water the plants". Can you note that she likes plants? | `list_allowed_directories`, `schedule_task` `at_time` 08:00, `spawn_subagents` | 0 rows, 1 daily item | daily, unkept | **unasked daily item; fact lost** |
| m5-2, m5-3 | as m5 | `schedule_task` `at_time` 08:00, `spawn_subagents` | 1 row, 1 daily item | none | **unasked daily item** |
| m6 | Mon collègue m'a dit « oublie ça », mais garde en mémoire que la réunion est jeudi. | none | 1 row | none | **reply: `J'oublie ce que vous venez de mentionner`** |
| m6-2, m6-3 | as m6 | none | 1 row | none | correct |
| m8, m8-2, m8-3 | Remind me Friday at 9 to move the car. | `schedule_task` `at` Friday 09:00 | 1 row, 1 item | none | correct |
| m9 | The note on my fridge says "don't save the receipts". Remember that the plumber comes on Thursday. | none | 1 row | none | correct |
| m10 | My sister always says "keep it simple". What does that phrase mean? | none | 1 row | none | correct |
| m11 | My mother always says "every day is a gift". What could I write on her birthday card tomorrow? | none | 1 row, 0 items | none | correct |
| m12 | Remind me tomorrow at 9 to move the car. | `schedule_task` `at` tomorrow 09:00 | 1 row, 1 item | none | correct |
| m13 | My colleague asked me "do you delete things when someone says forget?" What should I tell her? (seed) | none | seed kept, 1 row | none | correct |
| m15 | Tell my brother I said "forget it", and remember that he owes me 20 euros. (seed) | `list_allowed_directories` refused | seed kept, 1 row | none | correct |
| m14 | Last week I asked you to remind me every day at 7 to stretch. Did that ever work? | `list_scheduled` | 1 row, 0 items | none | correct |
| m16 | If I asked you to remind me every Monday, would that use a lot of memory? | none | 1 row, 0 items | none | correct |
| m17 | Mein Chef sagt immer „vergiss es“. Merk dir, dass das Meeting am Freitag ist. (seed) | none | seed kept, 1 row | none | correct |
| m18 | Don't forget: the dentist is on Friday at 10. | `list_scheduled`, `spawn_subagents` refused, `edit_scheduled` failed | 1 row, 0 items | none | correct |
| s1 | as m4, on the shell (seed) | none | seed kept, 1 row | none | correct |
| s2 | as m5, on the shell, new chat | `schedule_task` `at_time` 08:00 | 1 row, 1 daily item | none | **unasked daily item** |

## Counts

Of 25 turns (m1 to m18 with their repeats, s1, s2):

- **Forget cards**: 0. No message that quoted, reported or asked about forgetting led to a
  `forget_memories` call, and every seeded row was still stored after its flow (5 of 5).
- **Requests not to keep**: the quoted `don't save the receipts` (m9) withheld nothing; the fact
  beside it was stored.
- **Schedule items**: 4 of 4 turns quoting Anna's request to remind stored a daily reminder for
  the person (m5, m5-2, m5-3, s2); such a turn now closes with the note below.
  0 of 3 turns naming a repeat in a quote, a report of an earlier request or a hypothetical (m11,
  m14, m16) stored an item. m3 stored its reminder on the day of the reported clause, and the
  reply named that day.
- **Rows**: every turn asking to keep a fact stored its exchange except m5, whose unasked
  `list_allowed_directories` call left the turn tainted, so nothing was kept and the reply said
  `I've noted that you like plants` above the unkept note. `Can you note that ...?` is not read
  as a request to remember, filed as
  [R-1129](../refinements/tasks/1129-a-question-asking-to-note-a-fact-is-not-read-as-a-request-to-remember.md).
- **Notes**: every note shown was true (m5: daily and unkept). One reply claimed an action with no
  note: m6's present-tense French forget claim, 1 of 3 draws, filed as
  [R-1130](../refinements/tasks/1130-a-french-reply-saying-it-forgets-in-the-present-gets-no-note.md).

## The weekday read under the two schedule notes

`named_weekday` (`schedule_weekly.py`) reads the one weekday a message names only when no word of
`_MAY_REPEAT` stands anywhere in it. That list holds words such as `move`, `again`, `change`,
`push`, `first`, `last`, `later` and any word ending in `days`, so it reads no weekday in `Remind
me Friday at 9 to move the car.` Unit probes of 16 one-time requests naming Friday read no
weekday in 15 (`move the car`, `call Anna again`, `push the bins out`, `change the sheets`, `the
first appointment`, `the last train`, `the holidays`, `déplacer la voiture`, `das Auto zu
verschieben`). For the weekly refusal that is its safe side, since a refusal keeps the tool when
unsure. But `WEEKDAY_OFF_NOTE` and `FIRST_FIRE_NOTE` read the same function, and for a note the
safe side is to show: a one-time item stored a day off Friday, or a repeat first firing before
it, got no note whenever the message held one of those words.

Both notes now read `one_named_weekday`, the one weekday a message names whatever else it says;
the refusal and the weekly date keep `named_weekday`. Each note states only the date stored, so a
note shown where it was not needed is still true. Near misses written first as tests: two weekdays
named (`Move my Friday reminder to Saturday.`), `every Friday` stored on Friday, and `move the car`
stored on Friday show no note; `every day until Friday` stored daily shows the first fire note,
which is true and not needed. Replayed through both readers, 7,359 distinct strings from tonight's
and last night's driver rows and the readings: 102 read a weekday before and 132 after, none
changed its day, and the 30 added are weekly requests, edits naming one day (`Move it to
Monday.`) and the car request.

**Pass rule.** When a one-time item is stored a day off the one weekday the message names, or a
repeat first fires before it, the note shows whatever repeat or change word the message holds. The
form's frequency is a separate count: the model stored the car request on Friday in 3 of 3 draws
(m8), so these draws show no note on either build.

## The note after a reminder stored from quoted words

`quoted_stored_notes` (`schedule_quoted.py`) closes a turn whose `schedule_task` call succeeded
while the message asks to remind only inside quotation marks and holds words outside them,
naming the repeat and the time stored. Near misses written first as tests: a request outside the
quote (`Remind me at 8 to "water the plants".`, `Remind me to answer Anna's "call me at 8".`), a
quote holding no request, a request to wake beside a quoted one, and a message that is all quote
show no note; `"Remind me at 8," I told myself.` shows it, which is true and not needed. Replayed
through the reader, 105 distinct driver messages from tonight's and last night's rows: 1 read
(m5). With the readings' cells, 7 of 7,412 strings: the other 6 cite a message inside prose.

**Pass rule** (written before the draws). The note ships when it closes every draw of m5 that
stores a reminder and no near miss above shows it. How often m5 stores a reminder is a separate
count; a draw storing none counts for neither.

**Draws** on the rebuilt stack brain, 06:49 to 06:51, chats `s18-m5-1` to `s18-m5-3`, SM clock
0.57 of `clocks.max.sm`: 2 of 3 stored a daily reminder at 08:00 and both closed with the note,
so the note ships. The third called only `spawn_subagents` and stored nothing. In `s18-m5-1` the
daily note showed as well, true and not needed: `you like plants` makes `names_repeat` read the
sentence as a choice. `s18-m5-3` called `list_allowed_directories`, `list_directory` and
`read_text_file` twice beside `schedule_task` and stopped at the round cap with no answer, which
[R-1129](../refinements/tasks/1129-a-question-asking-to-note-a-fact-is-not-read-as-a-request-to-remember.md)
counts. Driver rows `rows.jsonl`, the replays `replay.py` and `rows.py` and the mutation rows
`mut.py` are in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/58410d85-0aa8-4ebe-9853-99c9c16a6905/scratchpad/slot18/`.

Driver rows `rows1.jsonl` to `rows3.jsonl`, frames `f02.png` and `f03.png`, the replay `replay.py`
and the probes in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/58410d85-0aa8-4ebe-9853-99c9c16a6905/scratchpad/slot17/`.
After the flows every `s17-*` row, both shell rows and every schedule item were deleted.
