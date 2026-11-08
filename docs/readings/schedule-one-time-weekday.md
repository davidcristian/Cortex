# Readings: a one-time reminder on a named weekday

Whether the cortex stores a request for one named weekday ("on Tuesday") as a one-shot, through
`at`, or as a rule that repeats on that weekday every week, through `at_time` with `on_days`, and
whether a request that names a weekly repeat keeps its rule. Read with
[ADR-0025](../adr/ADR-0025-scheduling-reminders.md); the tool is
`brain/packages/core/src/cortex_core/schedule_tools.py`.

## The rig

**2026-11-08**, the shared `cortexn16` stack: the resident cortex (gemma-4-12B, text only,
context 16384), both CPU subagent servers, the embedder, pgvector, Redis schedules with
`CORTEX_SCHEDULE_TZ=Europe/Berlin`, as in [side-effect-tools-second-clause.md](side-effect-tools-second-clause.md).
Each row goes over `Converse` from the stack's turn driver, one fresh chat per draw, every card
approved, and the stored item is read back from Redis by its `session_id`. The draws run on
Sunday 2026-11-08, so Tuesday is 2026-11-10, Thursday 2026-11-12 and Friday 2026-11-13.

## Rows and the rule, written before the first draw

| Row | Message | Draws | Stored as wanted |
| --- | --- | --- | --- |
| W1 | "Remember that I have the barber on Tuesday. Give me a shout at 8 that morning." | 2 | one-shot 2026-11-10 08:00 |
| W2 | "Remind me on Friday at 18:00 to call the plumber." | 2 | one-shot 2026-11-13 18:00 |
| W3 | "Rappelle-moi mardi à 9h d'appeler le dentiste." | 2 | one-shot 2026-11-10 09:00 |
| W4 | "Erinnere mich am Donnerstag um 7 Uhr an den Arzttermin." | 2 | one-shot 2026-11-12 07:00 |
| K1 | "Remind me every Tuesday at 8 to put the bins out." | 2 | a rule on Tuesday at 08:00 |
| K2 | "On Tuesdays at 8, remind me to water the plants." | 2 | a rule on Tuesday at 08:00 |
| K3 | "Rappelle-moi chaque mardi à 9h de sortir les poubelles." | 2 | a rule on Tuesday at 09:00 |
| K4 | "Erinnere mich jeden Dienstag um 7 Uhr an den Müll." | 2 | a rule on Tuesday at 07:00 |

The W rows name one weekday and no repeat; the K rows name a weekly repeat and must keep it.

**The form** is a W draw whose first `schedule_task` call holds `on_days`. Its count is recorded
for both builds and is not part of the pass rule, so a rare form still decides on what the change
does when it occurs.

**Pass rule for a change that reads the message against an `on_days` call:** it ships only if,
on the build, every one of the eight K draws stores its weekly rule with no refusal of any call, every
W draw stores a reminder, and every W draw that shows the form ends with a one-shot item on the
date and hour in the table and no weekly item. A baseline with no form in eight W draws leaves the
tool alone and the task open.

**Which shape is tried first.** The one recorded draw of W1 (02:39, chat `s3-c`) replied "every
Tuesday at 8:00 AM", so a note held back when the reply names the repeat, as the daily note is,
would not have shown, and the item would still fire every week. A typed refusal of the call, as
the monthly rule beside a yearly date is refused, changes what is stored, so it is built first;
the note stays the fallback if the refusal fails a K row.

**Second condition, written after the first build draw and before any draw under it.** The first
draw on the first build (chat `s4n-w1a`, 03:07) recalled the baseline chats' exchanges ("the user
has already asked for this twice"), and its retry after the refusal kept the weekly rule because
the result invited one: "If the person asked earlier in this chat for a weekly repeat, call again
with the same arguments". That sentence was removed. Under the second condition each chat's
memory rows and schedule items are deleted after its turn, so no draw recalls another. The pass
rule applies to the second condition. The next sentence was written after reading the second
condition's first draw (W1, no form) and before reading any other: if no W draw in it shows the
form, W1 is drawn four more times under the same condition, and the rule applies to those too.

**Third item, written after reading the second condition's first six draws and before reading
any later one.** K2a (`On Tuesdays at 8`) stored a daily rule, and its turn made one call with no
refusal, so the build ran the same request as the baseline and the item over a K row's stored rule
measured only draw noise there; as written, the rule fails on K2a. The K item is replaced by: no
call in any K draw is refused, with the stored rule counted separately. Under it, after the second
condition's sixteen draws, K1 to K4 are drawn once more and W1 four times, and the change ships
only if those draws pass the rule with this item.

## Results

Each cell counts draws. "form" is a W draw whose first call held `on_days`; "one-shot" an item
with no `rule`; "weekly" a rule on the named weekday and hour. SM clock during every draw: 0.57 of
`clocks.max.sm`. Chats `s4-*` (baseline), `s4n-*` (first build), `s4m-*` (second condition) and
`s4r-*` (replication).

| Run | W1 | W2 | W3 | W4 | K1 to K4 | Refusals |
| --- | --- | --- | --- | --- | --- | --- |
| baseline, HEAD | 2 form, 2 weekly | 2 one-shot | 2 one-shot | 2 one-shot | 8 weekly | none |
| first build, first condition | 1 form, refused, retry weekly | 1 one-shot | not drawn | not drawn | not drawn | 1 |
| second condition | 2 one-shot | 2 one-shot | 2 one-shot | 2 one-shot, one a day late | 7 weekly, K2a daily | none |

In the baseline each b draw found its a draw's item already on the schedule (the same text, due
time and rule), so it added none; that match is how its rule was read. The baseline's form
frequency is two of eight W draws, both W1; the second condition's is none of eight. W4a in the second
condition stored Friday 2026-11-13 for "am Donnerstag" with no refusal in its turn; the rows
below measure that late date.

| Run | W1 | K1 to K4 | Refusals |
| --- | --- | --- | --- |
| replication, second condition | 4 one-shot, no form | 4 weekly | none |

**Result.** The rule with the third item passes: no call in any of the twelve K draws on the
build was refused, and every W draw stored a reminder, all on the right weekday but W4a's. No W draw under the
second condition showed the form (0 of 12), so the item over what a refused call is retried with
is met by no draw; the one refused call (first condition) was retried weekly for the reason the
second condition removed. The replay rows B1 and B2 below measure that retry with the first call
fixed.
The replay of 9,099 distinct recorded draw messages, readings quotes and test strings through
`names_one_weekday` found 52 that name one weekday and no repeat word; none asks for a weekly
repeat. Run logs `base.log`, `build.log`, `build2.log`, `rep.log` and `replay2.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/5e7bbbe2-0692-4951-9718-a5c1c4b48de9/scratchpad/slot4/`.
Every `memories` row and schedule item of the draws was deleted afterwards.

## A one-time date on another weekday

Whether a one-time `at` the cortex writes for one named weekday falls on that weekday. Same rig
and second condition as above, on a second brain built from `838d7085c` that sends its requests
through the stack's recording proxy, chats `s5-*`.

**Rows, written before the first draw.** Each row is drawn four times; Thursday is 2026-11-12.

| Row | Message | Stored as wanted |
| --- | --- | --- |
| D1 | "Erinnere mich am Donnerstag um 7 Uhr an den Arzttermin." | one-shot 2026-11-12 07:00 |
| D2 | "Remind me on Thursday at 7 to call the doctor." | one-shot 2026-11-12 07:00 |
| D3 | "Rappelle-moi jeudi à 7h d'appeler le médecin." | one-shot 2026-11-12 07:00 |

**The form** is a draw whose first `schedule_task` call holds an `at` on a date that is not a
Thursday. Its count is recorded and is not part of the pass rule.

**Pass rule for a typed check of `at` against the one named weekday:** it ships only if, in unit
tests and in a replay where the first call is fixed to the wrong date, it refuses that call once
with a result naming the weekday the date falls on, the retry runs, and no call whose date is the
named weekday is refused in any D draw on the build.

**Replay rows, written after the D draws on the start build and before any replay.** Each row
sends one request recorded through the proxy from a second brain built from `838d7085c` straight
to the model host four times, with only the named message or result changed, and reads the next
call. Request 110 is draw D2c's second request: its first call was weekly and was refused.

| Row | Request | Next call wanted |
| --- | --- | --- |
| P1 | D2b's second request, its call's `at` set to 2026-11-13T07:00:00 and its result to the weekday refusal | `at` 2026-11-12T07:00 |
| P2 | D2c's third request, its second result set to the weekday refusal | `at` 2026-11-12T07:00 |
| B1 | request 110 as recorded | `at` 2026-11-12T07:00, no `on_days` |
| B2 | request 110 with the W1 barber message and a weekly call on Tuesday at 08:00 | `at` 2026-11-10T08:00, no `on_days` |

The P rows record what the cortex sends after the weekday refusal; a retry on another weekday
runs, because the refusal fires once per turn, and is counted. The B rows measure the retry after the weekly refusal:
they pass when every next call is a one-time `at` on the date in the table and none drops the
reminder.

## Results of the one-time date rows

Calls are read from the proxy's request log (start build) and the second brain's audit log
(build). SM clock 0.57 of `clocks.max.sm` in every draw. "weekly, then X" is a first call with
`on_days`, refused by the weekly check, then X.

| Run | D1 | D2 | D3 | Stored a day late |
| --- | --- | --- | --- | --- |
| start build `838d7085c`, chats `s5-*` | 4 Thursday | 2 Thursday; 1 weekly, then Friday | 3 Thursday; 1 weekly, then Thursday | 1 of 12 (D2c) |
| build with the weekday check, chats `s5b-*` | 4 Thursday | 1 asked "7 AM or 7 PM?"; 1 Thursday; 1 weekly, then Friday refused, then Thursday; 1 weekly, then Thursday | 4 Thursday | 0 of 12 |

| Replay row | Next call, four draws |
| --- | --- |
| P1 | 4 `at` 2026-11-12T07:00 |
| P2 | 4 `at` 2026-11-12T07:00 |
| B1 | 2 `at` 2026-11-12T07:00, 2 `at` 2026-11-13T07:00 |
| B2 | 3 `at` 2026-11-10T08:00, 1 `at` 2026-11-11T08:00 |

**Result.** The form, a first call with a one-time date off the named weekday, came in 0 of 24
draws. The late date in every draw where it came was the retry after the weekly refusal: D2c and
s5b-d2b live, and 3 of 8 B replays, none of which kept the weekly rule or dropped the reminder.
The B rows fail their rule, so the weekly refusal's text is measured again in rows B3 and B4.
The weekday check passes its rule: the unit tests refuse a wrong date once and run the retry,
every P replay retried on the right Thursday, s5b-d2b's late retry was refused and its next call
stored Thursday, and no call on the named weekday was refused in any build draw. After the build
draws the check was narrowed to a date one day either side of the named weekday, because "Note my
flight on Friday, then please ring me at 6" may mean today; no build draw's call is more than one
day off. The replay of 9,134 recorded strings found 55 that name one weekday and no repeat word,
46 of them with no word that moves the day. Logs `draws.log`, `draws-build.log`, `replay.log`
and `replay_msgs.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/5e7bbbe2-0692-4951-9718-a5c1c4b48de9/scratchpad/slot5/`; every row and item of the draws was deleted.

**Rows for a weekly refusal that names the date, written after the B results and before any draw
under them.** B3 and B4 are B1 and B2 with one sentence added to the refusal: "The next Thursday
is 2026-11-12." (B3) or "The next Tuesday is 2026-11-10." (B4), four draws each. They pass under
the B rule. A pass measures only the text; shipping it needs the person's zone in the dispatch
round, which the build under the live rows below adds.

| Replay row | Next call, four draws |
| --- | --- |
| B3 | 4 `at` 2026-11-12T07:00 |
| B4 | 4 `at` 2026-11-10T08:00 |

**Result.** B3 and B4 pass: with the date named, 8 of 8 retries were on it, against 5 of 8 for
the same requests without it (B1, B2). SM clock 0.57 of `clocks.max.sm`; log `replay2.log` in the
slot directory above.

**Live rows for the build, written before any draw on it.** The stack brain is rebuilt from the
working tree whose weekly refusal names the next date, counted in `CORTEX_SCHEDULE_TZ`
(Europe/Berlin) from the brain's clock. Second condition, chats `s6-*`. L1 is B1's message, "Remind
me on Thursday at 7 to call the doctor.", and L2 is B2's, the W1 barber message; eight draws each.
The form is a draw whose first `schedule_task` call holds `on_days`; its count is recorded and is
not part of the rule. Calls are read from the stack brain's audit log, items from Redis.

**Rule (the B rule, drawn live).** Every draw that shows the form ends with one one-shot item at
2026-11-12 07:00 (L1) or 2026-11-10 08:00 (L2) and no weekly item; no draw drops the reminder after
a refusal. A draw with no form is counted by what it stored and is not part of the rule. With no
form in sixteen draws the rule is met by no draw, and the replay rows B3 and B4 stay its evidence.

| Run | L1 | L2 | Refusals |
| --- | --- | --- | --- |
| build, chats `s6-*` | 7 Thursday; 1 weekly, then Thursday | 7 Tuesday; 1 weekly, then Tuesday | 2 weekly |

**Result.** The rule passes. The form came in 2 of 16 draws (s6-l1b, s6-l2b); each weekly call
was refused once and its retry stored a one-shot at 2026-11-12 07:00 and 2026-11-10 08:00, with no
weekly item. All sixteen draws stored a one-shot on the wanted date and hour. SM clock 0.53 to 0.57
of `clocks.max.sm`. Logs `draws.log`, `items.tsv` and `calls-live.txt` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/5e7bbbe2-0692-4951-9718-a5c1c4b48de9/scratchpad/slot6/`;
every row and item of the draws was deleted.
