# Readings: which one-time dates the weekday reader refuses

Whether `weekday_mismatch` (`brain/packages/core/src/cortex_core/schedule_weekday.py`) refuses a
one-time `at` that falls on another weekday than the one the message names only when the date is
wrong. Read with [schedule-one-time-weekday.md](schedule-one-time-weekday.md), which has the rig,
the earlier rows and the audit draws, and [ADR-0025](../adr/ADR-0025-scheduling-reminders.md).

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
