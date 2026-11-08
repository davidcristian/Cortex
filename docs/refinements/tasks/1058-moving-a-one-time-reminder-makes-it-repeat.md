# Moving a one-time reminder makes it repeat

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-08

`edit_scheduled` (`schedule_verbs.py`) has no way to move a one-time item to a new date or time.
Its only time argument, `at_time`, sets a wall-clock rule: with no day selector the rule repeats
every day from today, and with `on_days` every week. So a correction of a one-time reminder's time
or day turns it into a repeating one. Live flows on 2026-11-08, each in a new chat with every card
approved ([the readings](../../readings/overlay-corrections-flows.md)):

- t1: `Remind me on 14 December to send the parcel.` stored one item due 14 Dec 09:00 and showed
  the stored time note. `Change it to 3 in the afternoon.` called `edit_scheduled` with `at_time`
  15:00. The item became a daily rule due 8 Nov 15:00, and the reply said "I've changed the
  reminder to 3:00 PM on 14 December."
- t2: the same in French (`Mets-le plutôt à 15 h.`) gave the same daily rule and "il est
  maintenant prévu pour le 14 décembre à 15h00".
- x1 and a flow on the Linux shell: `Remind me on Tuesday at 9 to call mom.` (or `the dentist`)
  stored a one-time item on 10 Nov. `No, I meant Wednesday.` called `edit_scheduled` with
  `at_time` 09:00 and `on_days` `["wed"]`. The item became a weekly rule, and the reply said "It's
  now set for Wednesday, November 11th, at 9:00 AM." with no repeat named.

When the model instead cancels the item and schedules a new one (flows w1, w2 and x2), the result
is right, but the cancel shows a card saying the delete has no undo. Since 2026-11-08 a reply over
the daily form ends with `DAILY_STORED_NOTE` when it names no repeat; the weekly form gets no note,
and the daily note's own follow-up (`every_seconds` 0) keeps today's due time, not the old date.

## What to do

1. Give `edit_scheduled` a way to set a one-time item's new date and time, such as an `at`
   argument read as `schedule_task` reads its `at`, with its contract test and fake.
2. Decide what `at_time` alone, or with one weekday, does on a one-time item when the message
   names no repeat: keep it one time on the new date and time, or refuse with a result naming
   `at`, as `schedule_weekly.py` refuses a weekly rule. Record the choice in ADR-0025.
3. Rerun flows t1, t2 and x1 of the readings and count items that stay one time.

## History

- 2026-11-08: filed from flows t1, t2 and x1 and a shell flow in
  [the readings](../../readings/overlay-corrections-flows.md); the same slot made `daily_after`
  read the daily form, so its reply closes with the daily note.
