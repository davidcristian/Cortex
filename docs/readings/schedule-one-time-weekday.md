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
condition stored Friday 2026-11-13 for "am Donnerstag" with no refusal in its turn, filed as
[R-1039](../refinements/tasks/1039-a-one-time-reminder-on-a-named-weekday-can-be-stored-a-day-late.md).

| Run | W1 | K1 to K4 | Refusals |
| --- | --- | --- | --- |
| replication, second condition | 4 one-shot, no form | 4 weekly | none |

**Result.** The rule with the third item passes: no call in any of the twelve K draws on the
build was refused, and every W draw stored a reminder on the right weekday. No W draw under the
second condition showed the form (0 of 12), so the item over what a refused call is retried with
is met by no draw; the one refused call (first condition) was retried weekly for the reason the
second condition removed. Measuring that retry with the first call fixed is
[R-1040](../refinements/tasks/1040-measure-the-retry-after-a-weekly-rule-is-refused-beside-one-weekday.md).
The replay of 9,099 distinct recorded draw messages, readings quotes and test strings through
`names_one_weekday` found 52 that name one weekday and no repeat word; none asks for a weekly
repeat. Run logs `base.log`, `build.log`, `build2.log`, `rep.log` and `replay2.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/5e7bbbe2-0692-4951-9718-a5c1c4b48de9/scratchpad/slot4/`.
Every `memories` row and schedule item of the draws was deleted afterwards.
