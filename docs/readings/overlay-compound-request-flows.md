# Readings: compound requests, through the brain and the overlay

What one message does when it needs two or three capabilities at once: remember a fact, set a
reminder, read a file, forget a fact. For each turn: which capability ran, what `memories` and
the schedule held afterwards, and whether the closing notes were true and agreed with each other.
Scheduling is in [ADR-0025](../adr/ADR-0025-scheduling-reminders.md), the refusals on a request
to remember in [ADR-0013](../adr/ADR-0013-untrusted-content.md), the closing notes in
[closing-note-language.md](closing-note-language.md).

## The rig

**2026-11-10**, the `cortexn18` GPU stack at the tree of that night: the resident cortex
(gemma-4-12B) at a context of 16,384 tokens, memory on pgvector with the default `global` scope,
the filesystem sidecar over a scratch root holding `notes.txt` (three lines: `Cortex test
notes.`, a landlord meeting on Thursday, a shopping list), Redis schedules with
`CORTEX_SCHEDULE_TZ=Europe/Berlin`. The turns ran on Tuesday at 04:52 to 05:03 local time. A
host driver sent each turn over `Converse` with every card approved, one chat per turn
(`s11-<flow>`), and two turns ran on the Linux shell
([body-overlay.md](../runbooks/body-overlay.md#the-tauri-app-on-linux-headless)) on `Xvfb`. SM
clock 0.57 to 0.72 of `clocks.max.sm`. The first two batches kept their rows between turns; from
the third batch on, every row and schedule item was deleted before each turn.

## Turns

| Flow | Message | Calls | Stored | Notes | Result |
| --- | --- | --- | --- | --- | --- |
| c1 | Remember that my locker code is 4417 and remind me at 18:00 to empty the locker. | `schedule_task` `at_time` 18:00 | 1 row, 1 daily item | daily | the message asked for one time |
| c2 | Read notes.txt and remind me tomorrow at 9 of the first item in it. | 3 file calls, `schedule_task` `at_time` 09:00 | 0 rows, 1 daily item first due today | daily | reply said tomorrow ([first fire](schedule-daily-first-fire.md)) |
| c3 | Forget my old locker code 4417, remember the new one is 5528, and remind me Friday to test it. | `forget_memories` `4417` (card: 2 rows), `schedule_task` `at` Friday 09:00 | 0 rows, 1 item | unkept | correct |
| c4 | Remind me at 7 to call Anna and don't save anything else from this message. | `schedule_task` `at` today 07:00 | 0 rows, 1 item | none | correct |
| c5 | What's in notes.txt? Also, forget what I told you about my bike. | 4 file calls, `forget_memories` `bike` (card: 1 row) | 0 rows | none | correct |
| c6 | Souviens-toi que le code de mon casier est 4417 et rappelle-moi demain à 9h de vider le casier. | `spawn_subagents` refused | 1 row, 0 items | **none** | false schedule claim ([refused fan-out](spawn-refused-on-remember.md)) |
| c7 | Vergiss meinen alten Spindcode 4417, merk dir, dass der neue 5528 ist, und erinnere mich am Freitag daran, ihn zu testen. | `forget_memories` `4417` (card: 1 row, 1 kept), `spawn_subagents` refused | 1 row (kept), 0 items | unkept, numbers left | no reminder, the reply said so ([refused fan-out](spawn-refused-on-remember.md)) |
| c2b | as c2 | 3 file calls, `schedule_task` `at` tomorrow 09:00 | 0 rows, 1 item | none | correct |
| c2c | Remember that I park on level 3 and remind me tomorrow at 9 to move the car. | `schedule_task` `at_time` 09:00 | 1 row, 1 daily item first due today | daily | reply said tomorrow (first fire) |
| c2d, c2e | as c2c | `schedule_task` `at` tomorrow 09:00 | 1 row, 1 item | none | correct |
| c6b, c6c | as c6 | `schedule_task` `at` tomorrow 09:00 | 1 row, 1 item | c6b: time | correct |
| s1 | as c1, on the shell | `spawn_subagents` refused, then `schedule_task` `at_time` 18:00 | 1 row, 1 daily item | none | reply said daily; one time asked |
| s2 | What's in notes.txt? Also, forget what I told you about my locker. (shell, new chat) | 3 file calls, no forget call | s1's row still stored | unforgotten | reply claimed a removal; the note held |

Seeds before c3, c5 and c7 (`Remember that my locker code is 4417.`, the bike, `Merk dir, dass
mein Spindcode 4417 ist.`) each stored one row. Controls: `Remind me tomorrow at 9 to move the
car.` twice, each stored `at` tomorrow 09:00 with no note. On a brain built after the reader
change below, the c6 message three more times (f1 to f3): f1 stored `at_time` 09:00 first due
today under a reply saying `demain à 9h00` (first fire), f2 and f3 stored `at` tomorrow 09:00.

## Counts

Of 18 compound turns (c1 to c7, c2b to c2e, c6b, c6c, f1 to f3, s1, s2):

- **Every capability ran, or the reply or a note said it had not**: 17 of 18. The exception is
  c6, a French schedule claim with no call and no note.
- **Rows**: every turn asking to keep a fact with no forget stored one row of the exchange (c1,
  c2c to c2e, c6, c6b, c6c, f1 to f3, s1); the turns that forgot stored none (c3, c7: the new
  value was withheld, as the reply and `UNKEPT_CLAIM_NOTE` said); c4's request not to keep
  stored none; the file turns stored none.
- **Schedule shape**: 5 of 14 turns that made a schedule call stored a daily item for a one-time
  request (c1, c2, c2c, f1, s1), against 0 of 2 single requests. The `at 18:00` form was stored
  daily 2 of 2 and `tomorrow at 9` 3 of 10. Each daily item ended with `DAILY_STORED_NOTE` or a
  reply naming the daily repeat; the three for tomorrow first fire today, which
  `FIRST_FIRE_NOTE` now names ([schedule-daily-first-fire.md](schedule-daily-first-fire.md)).
- **Refused fan-out**: `spawn_subagents` was called and refused in 3 turns (c6, c7, s1); the
  reminder after it was claimed with no call once, dropped with a true reply once, and stored by
  a direct call once.
- **Notes**: 0 turns with two notes that contradict each other. Two notes were true and not
  needed: the time note after `demain à 9h de vider` (c6b) and after `**9h00**` (f1), since
  `names_time_of_day` reads neither as a time ([R-999](../refinements/tasks/999-a-note-the-brain-appends-is-english-under-a-reply-in-another-language.md)).
  c3 and c7 ended with the English `UNKEPT_CLAIM_NOTE`, c7 under a German reply (R-999).

## The French claim with an object pronoun

c6's reply, `Je vous ai également programmé un rappel pour demain à 9h00 pour "vider le
casier".`, was not read as a claim, because `claims_scheduled_other` named only `j'ai` and
`c'est` with `bien`, `aussi` or `déjà` before the participle. It now reads an object pronoun
before the auxiliary (`je vous ai`, `je t'ai`, `nous vous avons`) and up to two words after it,
so `UNSCHEDULED_CLAIM_NOTE` shows on that reply when no scheduling call succeeded. Near misses
were written first: a question, a negation, `je vous ai envoyé`, `je vous ai demandé`, a
condition, a future form. Every distinct readings string and this night's replies (29,739)
were replayed through the old and the new reader: 27 claims became 29 and none was lost; the two
added are c6's reply and c6c's `J'ai également programmé un rappel [...]`, a true claim after a
call, which shows no note. Scripts `rp.py` and `mut.py` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/58410d85-0aa8-4ebe-9853-99c9c16a6905/scratchpad/slot11/`,
driver rows `rows1.jsonl` to `rows4.jsonl` beside them.

After the flows every `s11-*` row, both shell rows and every schedule item were deleted.

## Smoke flow over the night's changes, 2026-11-10

The same rig at the tree of the night's last code change, Tuesday 07:49 to 07:55 local time, SM
clock 0.57 to 0.63 of `clocks.max.sm`. One chat per turn (`s22-<turn>`) through the driver with
every card approved, and sh1 and sh2 on the Linux shell, each in a new chat. Seeds: t1's row
for t2 and t3; one message naming both numbers for t4; one row each for t4b
(`Remember that my savings account number is 015 123 456 789.` and `Remember that my library
card number is 0151234567890.`); `Remember that my gym is on Elm Street.` for t5; sh1's row for
sh2. Rows and items were deleted after each flow.

| Turn | Message | Calls | Stored | Notes | Result |
| --- | --- | --- | --- | --- | --- |
| t1 | Remember that my locker code is 4417. | none | 1 row | none | correct |
| t2 | What is my locker code? (new chat) | none | 1 row, answered 4417 | none | correct |
| t3 | My locker code is 4471, not 4417. | `list_directory_with_sizes` failed, `spawn_subagents` | 0 rows, t1's 4417 row kept | unkept | reply says noted; the note is true |
| t4 | Forget 015 123 456 789. | `forget_memories` (card: 1 row, both numbers) | 0 rows | unkept, forget count 1 | correct, unkept note not needed |
| t4b | Forget 015 123 456 789. | `forget_memories` (card: 1 row) | the library card row kept | none | correct |
| t5 | Forget my bike lock code. | `forget_memories`, no match | gym row kept | unfound | correct |
| t6 | Remember that the plumber is called Marco, and remind me tomorrow at 9 to call him. | `schedule_task` `at` tomorrow 09:00 | 1 row, 1 item | none | correct |
| t7 | Anna said: "remind me tomorrow at 8 to water the plants". Can you note that she likes plants? | `schedule_task` `at` tomorrow 08:00 | 1 row, 1 item | quoted | reply says the reminder is for her; the note says it is for you |
| t8 | Erinnere mich jeden Montag um 8 Uhr daran, den Müll rauszubringen. | `schedule_task` `at_time` 08:00, `on_days` mon | 1 row, 1 weekly item first due Monday | none | correct |
| t9 | Souviens-toi que mon code de casier est 5521. | none | 1 row, French reply | none | correct |
| sh1 | as t6, on the shell | `spawn_subagents` refused, `schedule_task` `at` tomorrow 09:00 | 1 row, 1 item | none | correct |
| sh2 | as t5, on the shell | `forget_memories`, no match | sh1's row kept | unfound | correct |

Of 12 turns: every capability asked for ran, or a note said what did not happen, 12 of 12.
Every request to keep a fact stored one row (t1, t6, t7, t9, sh1). 4 of 4 reminder requests
stored the day and time asked, none as a daily item. The forget of a value written in groups
deleted only the row holding that text when the longer number had a row of its own (t4b); t4's
row held both, as its card listed. 6 notes in 12 turns, all true, 0 contradicting another; one
was not needed (the unkept note under t4's `I've updated your memories.`, which the update
claim reader shows by design). t3 is the form counted in
[correction-keeps-old-value.md](correction-keeps-old-value.md) (a turn kept out after a file or
subagent tool), filed as [R-1062](../refinements/tasks/1062-a-correction-of-a-stored-value-says-updated-and-keeps-the-old-row.md)
and [R-1116](../refinements/tasks/1116-an-update-of-a-stored-value-can-search-files-until-the-round-cap.md).
No new defect. Driver rows `rows.jsonl` and `rows2.jsonl` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/58410d85-0aa8-4ebe-9853-99c9c16a6905/scratchpad/slot22/`.
