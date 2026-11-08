# Readings: which one-time dates the weekday reader refuses

Whether `weekday_mismatch` (`brain/packages/core/src/cortex_core/schedule_weekday.py`) refuses a
one-time `at` that falls on another weekday than the one the message names only when the date is
wrong. Read with [schedule-one-time-weekday.md](schedule-one-time-weekday.md), which has the rig,
the earlier rows and the audit draws, and [ADR-0025](../adr/ADR-0025-scheduling-reminders.md). Its last
section replaces the refusal with a note.

## The evidence before the change, 2026-11-08

A date one day off the named weekday has two common intents: a wrong date, or a reminder for the
day before or after the thing. Every wrong date the cortex wrote in tonight's draws was the day
after the named weekday: W4a (Friday for Thursday, a first call), D2c and s5b-d2b (Friday for
Thursday, retries after the weekly refusal) and the 3 late B1 and B2 replays. Both refusals of a
correct call in the audit draws were a date before the named weekday: today for Monday's bins
and Monday for Tuesday's dentist. No draw or replay wrote a wrong date the day before.

The retries after the weekly refusal, which made five of those six late dates, were on the named
date in 8 of 8 B3 and B4 replays and 16 of 16 L draws once that refusal named the date. The first
call off the named weekday came in 1 of 62 draws of the W, D and L rows (W4a). So the weekday reader still
catches a real form, rarely.

**Shapes compared.** (a) Refuse only a date the day after the named weekday, and never a date
that is today in the person's zone. (b) Run the call and append a note naming the stored weekday
and date. (c) Remove the check. (c) stores W4a's form a day late and shows nothing. (b) shows it
but leaves it wrong, while the P replays moved 8 of 8 refused late dates onto the named day. (a)
keeps every refusal of a late date recorded tonight and none of the refusals of a correct call,
so it is built first; (b) is the fallback if a row below fails.

## Rows and the rule, written before the first draw

The stack brain rebuilt from the build, Sunday 2026-11-08, one new chat per draw, every card
approved, the stored item read from Redis by its `session_id` and the calls from the brain's
`tool.invocation` log lines. Each chat's rows and items are deleted after its turn.

| Row | Message | Draws | Stored as wanted |
| --- | --- | --- | --- |
| T1 | `Remind me at 6pm to put the bins out for Monday's collection.` | 2 | one-shot 2026-11-08 18:00 |
| T2 | `Rappelle-moi à 18h de sortir les poubelles pour la collecte de lundi.` | 1 | one-shot 2026-11-08 18:00 |
| T3 | `Erinnere mich um 18 Uhr daran, den Müll für die Abholung am Montag rauszustellen.` | 1 | one-shot 2026-11-08 18:00 |
| T4 | `Remind me at 6pm to return the chairs from Saturday's party.` | 2 | one-shot 2026-11-08 18:00 |
| T5 | `Remind me on Thursday at 7 to call the doctor.` | 2 | one-shot 2026-11-12 07:00 |

T1 is the audit's failed row and T5 the row that started the weekday reader. On the start build
the reader refuses the call T1 to T4 want (the replay below shows it for every one), so a start
build draw measures only what the cortex does after a refusal, which the audit recorded.

**Pass rule.** The build ships only if no call in any T draw is refused by the weekday reader,
every T1 to T4 draw stores one one-shot at 2026-11-08 18:00 or stores nothing after asking a
question, and every T5 draw stores one one-shot at 2026-11-12 07:00. In unit tests the build must
refuse a date the day after the named weekday once and run the retry. **The form** for T5, a
first call whose `at` is not on Thursday, is counted and is not part of the rule.

**Replaced item, written after reading the first three draws (s10-t1a, s10-t1b, s10-t2a) and
before reading any later one.** s10-t1a's first and only call wrote `at` 2026-11-09T18:00, Monday,
with no refusal. Its first request is the same on both builds and a date on the named weekday is
never read by either, so the item over T1 to T4's stored date measured only draw noise there; as
written, the rule fails on s10-t1a. The item is replaced by: in every T1 to T4 draw the stored
one-shot has the date and hour of the turn's first `schedule_task` call, so no call is moved.
Under it, after the eight draws, T1 to T4 are drawn once more each, and the change ships only if
all twelve draws pass the rule with this item.

**Second replacement, written after reading s10-t3a to s10-t4b and before reading s10-t5a or
any later draw.** s10-t3a and s10-t4a stored a daily rule at 18:00 from a first and only call
with `at_time` and no `at`, which neither build's weekday reader reads, so "one-shot" in the
replaced item again measured the first call. The rule's items become: no call in any T draw is
refused by the weekday reader, and each T draw stores exactly what its first `schedule_task` call
asked for, unless that call is the day after the named weekday and not today, when the retry
after the refusal must be on the named weekday. The four further draws are made under this rule.

## Results

On the stack brain built from the working tree at 06:02 (image `58d28ffba420`, which also has the
night's earlier fixes), chats `s10-*`. SM clock 0.57 of `clocks.max.sm` between turns.

| Row | Draws | First call | Refused | Stored |
| --- | --- | --- | --- | --- |
| T1 | 3 | 2 `at` 2026-11-08T18:00, 1 `at` 2026-11-09T18:00 | none | each as its first call |
| T2 | 2 | 1 `at` 2026-11-08T18:00, 1 `at_time` 18:00 | none | each as its first call |
| T3 | 2 | 1 `at` 2026-11-08T18:00, 1 `at_time` 18:00 | none | each as its first call |
| T4 | 3 | 2 `at` 2026-11-08T18:00, 1 `at_time` 18:00 | none | each as its first call |
| T5 | 2 | 1 `at` 2026-11-12T07:00, 1 no call (asked "7:00 AM or 7:00 PM?") | none | the one-shot, and nothing |

**Result.** The rule with the second replacement passes: no call in the twelve draws was refused,
and each draw stored what its first call asked for. The form for T5 came in 0 of 2. The replay of
the eleven recorded calls through both readers: the start build's refuses 6 (every `at` dated
today), this build's refuses none. The three `at_time` calls stored a daily rule, and the reply
of each closed with the daily note. Unit level, the old reader refused 85 of 85 recorded strings
naming one weekday with no moving word for a date the day before, and the new one refuses none;
both refuse all 85 the day after when it is not today. Logs `draws.log`, `draws2.log`,
`items.tsv`, `items2.tsv`, `replay2.log` and `replay3.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/5e7bbbe2-0692-4951-9718-a5c1c4b48de9/scratchpad/slot10/`; every row and item of the draws was deleted.

## Audit, 2026-11-08

Unit probes of messages that ask for the day after the named weekday in words the reader did not
read: `next morning`, `afterwards`, `when Monday is over`, `once the deadline has passed` and the
French `le matin suivant`. Each refused a correct date the day after, and the refusal asks for the
named day. These words now move the day. Replayed through the start and the new reader, 4998
quoted strings from tonight's and last night's drivers, the readings and the schedule tests: none
changed except the six audit probes. Still refused, and filed as a task: a possessive weekday
naming an event the day before (`follow up on Monday's call`, `once Monday's payday has cleared`),
the same form as the bins row above. On the safe side, `named_weekday` reads no weekday, so
neither refusal runs, for one-time requests holding `forever`, `always`, `move` or `change`
(4 of 6 probes), and `in advance` in `Remind me Friday at 9 to pay in advance.` keeps any date
(2 of 2). Probes in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/5e7bbbe2-0692-4951-9718-a5c1c4b48de9/scratchpad/slot13/`.

The same audit found the reader took the hour and weekday of an `at` with an offset as written,
while the schedule tool and `today` count the date in `CORTEX_SCHEDULE_TZ`. With the zone
`America/Los_Angeles`, `Remind me Monday at 9pm to call mum.` with `at` `2026-11-10T05:00:00Z`
(Monday 21:00 there) was refused as a Tuesday. An offset `at` is now read in the person's zone; a
naive `at` is already local. In `Europe/Berlin` the two dates agree at every hour from 04:00 to
21:59, so no recorded draw changes.

Three live turns on the stack brain built from that commit (chats `s13-a` to `s13-c`, SM clock
0.57 of `clocks.max.sm`) ran each first call with no refusal: `next morning` after Monday's
meeting stored Monday 09:00, `clean up afterwards` after Friday's party stored Friday 23:00, and
`when Monday is over` stored Monday 20:00. None was the day after the named weekday, so the start
reader would not have refused them either; the first is the model reading `next morning` as
tomorrow, which no reader checks. Their items were cancelled and their rows deleted.

## The refusal or a note, 2026-11-08

`_MOVES_DAY` grew three times tonight, each time because the refusal moved a correct reminder for
the day after an event onto the named day: the bins row, the audit's words above, and
`follow up on Monday's call`. Three shapes are compared over every recorded call: (a) keep the
refusal and add that task's words; (b) run every call and, after the turn, append a note naming
the stored weekday and date when a one-time item falls one day before or after the one weekday the
message names, with no word list; (c) remove the check.

**Rows and the rule, written before the replay.** The replay reads every one-time item tonight's
draws stored (the `items*.tsv` files of slots 4 to 13, joined to the message by chat) and the
audit probes (that task's three messages and the bins message, each with `at` the day after, on
Sunday 2026-11-08). It counts each item's date against the named weekday (on it, a day before, a
day after, other) and what each shape does with it.

- (b) passes when its note shows on every replayed item one day off the named weekday, no item is
  refused or moved, and no item on the named weekday has the note. How many items are one day off
  is counted apart and is not part of the rule.
- (a) passes only when it refuses no item whose date the person wanted.
- (c) is chosen only when no stored item was a day late, first call or retry, once the weekly
  refusal named the date.

**Results of the replay.** 78 stored one-time items, one per chat and date, and the four probes.
Script `replay3.py` and log `replay3.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/5e7bbbe2-0692-4951-9718-a5c1c4b48de9/scratchpad/slot14/`.

| Date against the named weekday | Items | Refused by (a) as it stands | Note by (b) |
| --- | --- | --- | --- |
| on it | 68 | 0 | 0 |
| a day before | 5 | 0 | 5 |
| a day after | 6 | 4 | 6 |
| no single weekday read | 3 | 0 | 0 |

Of the 11 items a day off, 8 are the date the person wanted: the bins on Sunday evening for
Monday's collection (4, in three languages), the chairs on Sunday after Saturday's party (2), the
agenda in two hours (1) and `follow up on Monday's call` on Tuesday (1). 3 are wrong: W4a and D2c,
Friday for Thursday, and the bins probe on Tuesday. (a) as it stands refuses the 3 wrong ones and
the follow up probe; with that task's words it would refuse only the 3, so (a) passes on this
replay, as it passed each time before a new form appeared. (b) passes: the note on 11 of 11 items
a day off, on none of the 68 on the named weekday, and nothing refused or moved. For (c), no item
stored after the weekly refusal named the date was a day late, but W4a's form is a first call,
which that refusal does not reach, and (c) would show it nothing.

**Decision: (b).** Both (a) and (b) pass on the replay. (b) is built because its rule holds for a
correct reminder a day off in any words, while (a) holds only for the words its list has, and
each of its three widenings tonight followed a correct reminder it moved. The cost is that a
wrong date a day off is no longer moved onto the named day, as 8 of 8 P replays did; the note
names it instead. That form came as a first call in 1 of the 62 draws of the W, D and L rows. The two other
probes (`once Monday's payday has cleared`, `post Monday`) read no single weekday on this tree, so
neither shape acts on them.

**Live rows for the note, written before any draw on it.** The stack brain rebuilt from the
working tree with the note, one new chat per draw, every card approved, each chat's rows and items
deleted after its turn; model time capped at 10 minutes.

| Row | Message | Draws |
| --- | --- | --- |
| N1 | `Remind me at 9 to follow up on Monday's call.` | 2 |
| N2 | `Remind me on Thursday at 7 to call the doctor.` | 2 |
| N3 | `Erinnere mich am Donnerstag um 7 Uhr an den Arzttermin.` | 1 |
| N4 | `Remind me at 6pm to put the bins out for Monday's collection.` | 1 |

**Rule.** No call is refused by a weekday reader; every draw whose stored one-time item is a day
off the named weekday ends its reply with the note naming that item's weekday and date in the
message's language; no draw whose item is on the named weekday shows it. How many items are a
day off is counted apart.

| Row | Stored | Note |
| --- | --- | --- |
| N1 | 2 one-shots at Sunday 2026-11-08 09:00, a day before Monday | 2 of 2, "on Sunday 2026-11-08" |
| N2 | 2 one-shots at Thursday 2026-11-12 07:00 | 0 of 2 |
| N3 | 1 one-shot at Thursday 2026-11-12 07:00 | 0 of 1 |
| N4 | 1 one-shot at Sunday 2026-11-08 18:00, a day before Monday | 1 of 1 |

**Result.** The rule passes: no call was refused, the note closed all 3 replies whose item was a
day off and none of the 3 on Thursday. Both N1 draws stored today for a follow up after Monday's
call, which is likely not the day the person meant; the old reader did not refuse a date that is
today, and the note now names it. SM clock 0.51 to 0.57 of `clocks.max.sm`. Chats `s14-*`, log
`draws.log` in the slot directory above; every item was cancelled and every row deleted.
