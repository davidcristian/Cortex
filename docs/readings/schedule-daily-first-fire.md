# Readings: a repeat whose first fire comes before the day the message names

`schedule_task` with `at_time` and no `starting` first fires at the next `HH:MM`, which is today
when that time has not passed. A message asking for one time tomorrow at 9, sent before 09:00 and
stored that way, first fires today and every day after. The compound flows recorded it in 3 of 10
turns asking for tomorrow at 9
([overlay-compound-request-flows.md](overlay-compound-request-flows.md#counts)); each reply said
tomorrow and `DAILY_STORED_NOTE` named no first day. The closing notes are in
[closing-note-language.md](closing-note-language.md), start dates in
[schedule-start-dates.md](schedule-start-dates.md).

## Shapes compared, 2026-11-10

(a) Run every call and, after the turn, append a note naming the first fire's weekday, date and
time when a repeat stored this turn first fires on a day before the one the person's message
names: tomorrow or the day after tomorrow in the five note languages, or the one weekday
`named_weekday` reads. Nothing is refused or rewritten. (b) Change `DAILY_STORED_NOTE` to always
name the first fire. (b) adds a date to every daily item, including the 2 of 2 `at 18:00` items
and every correct daily request, and still does not say the first fire is earlier than the day
asked for. (a) shows only where the stored first day differs from the named one, so (a) is built.
Its safe direction is to show: the note says only what was stored and invites no destructive step.

## Rule and rows, written before the build and any draw

Unit tests first, as near misses: a daily request `every day at 9 starting tomorrow` stored with
`starting` (no note) and without it (the note, since it first fires today), `remind me at 9` with
no day (no note), a one-time item for tomorrow stored with `at` (no note), a message naming today
or today's weekday (no note), `por la mañana` and `jeden Morgen` naming a morning (no note), and a
first fire already tomorrow because 09:00 has passed (no note).

Live rows on the stack brain rebuilt from the build, Tuesday 2026-11-10 before 09:00 local, one new
chat per draw, every card approved, each chat's rows and items deleted after its turn; model time
capped at 20 minutes.

| Row | Message | Draws |
| --- | --- | --- |
| R1 | `Read notes.txt and remind me tomorrow at 9 of the first item in it.` | 4 |
| R2 | `Remember that I park on level 3 and remind me tomorrow at 9 to move the car.` | 4 |
| R3 | `Souviens-toi que le code de mon casier est 4417 et rappelle-moi demain à 9h de vider le casier.` | 4 |
| C1 | `Remind me tomorrow at 9 to move the car.` | 2 |

**Pass rule.** The build ships only if every draw whose stored repeat first fires today ends its
reply with the note naming today's date and 09:00, no draw whose item first fires tomorrow shows
it, and every stored item is what the turn's `schedule_task` calls asked for, so no call is
refused or changed. **The form**, a draw storing a daily item that first fires today, is counted
apart and is not part of the rule, so the build ships even if the form does not come. A draw that
stores nothing is a null, counted apart. R3's note is English until the four other languages have
wording.

**Replaced item, written after reading draw r1-1 and before reading the reply or notes of any
other draw.** r1-1 stored `at_time` 09:00, then `edit_scheduled` with `every_seconds` 0 made it
one time, as the daily confirmation offers, so the item still fires today at 09:00 under a reply
saying tomorrow. An `every_seconds` change leaves the due time alone, but the build dropped the
item's first fire on any edit. The rule's first item becomes: every draw whose stored item, a
repeat or one time made from one in the same turn, first fires today ends with the note. The
build keeps the first fire across an edit that changes only `every_seconds`, and the 14 draws are
made again on it; the first build's draws are counted apart.

## Results, 2026-11-10

Chats `s12-r*` and `s12-c*` on the first build (05:10 to 05:14 local, image built 05:10), chats
`s12-b*` on the second (05:16 to 05:19, container `e5209b7105b3`). SM clock 0.57 to 0.62 of
`clocks.max.sm`. Calls are from the brain's `tool.invocation` log lines, which exist for the
second build only.

| Build | Daily, first fire today | Once, today | Weekly rule | Once, tomorrow | Nothing stored |
| --- | --- | --- | --- | --- | --- |
| first | 3 (r1-2, r3-2, r2-3), note 3 of 3 | 2 (r1-1, r1-3), note 0 of 2 | 1 (r1-4, Thursday, named in the reply) | 8, note 0 of 8 | 0 |
| second | 5 (br1-1 to br1-4, br2-2), note 5 of 5 | 0 | 1 (br2-4, Wednesday starting tomorrow) | 7, note 0 of 7 | 1 (br3-4) |

**Result.** The rule passes on the second build: the note closed 5 of 5 replies whose item first
fires today and none of the 8 whose item first fires tomorrow (br2-4's weekly rule among them);
each stored item is what the turn's successful `schedule_task` call asked for, since the note
refuses and changes nothing. The form came in 5 of 12 R draws on the second build (R1 4 of 4, R2
1 of 4, R3 0 of 4) and 0 of 2 controls; on the first build 3 of 12 daily and 2 one time today. The
replaced item's form, one time made from a repeat by an interval edit, came in 0 of 14 second
build draws and is checked by unit tests. Three findings are filed: br2-4's weekly rule for one
time tomorrow showed no note
([R-1125](../refinements/tasks/1125-a-one-time-request-for-tomorrow-stored-weekly-shows-no-note.md)),
r1-3 stored one time today by a path with no log
([R-1126](../refinements/tasks/1126-a-one-time-item-for-tomorrow-stored-for-today-may-show-no-note.md)),
and the note is English under a French reply
([R-1124](../refinements/tasks/1124-the-first-fire-note-is-english-in-every-language.md)). br3-4
claimed a reminder with no call and `UNSCHEDULED_CLAIM_NOTE` showed.

`days_named` over 6,952 quoted strings from `docs/` and every night's slot drivers read a day in
61; each string holding `morgen` or `mañana` that it read as tomorrow names tomorrow, and the two
it read as none are `jeden Morgen` and `por la mañana`. Rows `rows.jsonl`, `rows2.jsonl`, the
brain log `brain2.log`, `count.py`, `replay.py` and `mut.py` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/58410d85-0aa8-4ebe-9853-99c9c16a6905/scratchpad/slot12/`;
every `s12-*` row and schedule item was deleted.
