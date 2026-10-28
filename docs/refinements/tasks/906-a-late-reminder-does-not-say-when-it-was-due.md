# A late reminder does not say when it was due

**Status:** done 2026-10-28
**Area:** scheduling
**Origin:** [ADR-0066](../../adr/ADR-0066-reminder-toast-and-card.md)

A reminder that falls due while the brain cannot run, as across a sleep of the machine, fires
within one poll once the brain runs again. Its toast title names the due time when the fire is
late (decision 11 of ADR-0066, `late_phrase`), but the overlay's card shows the text and an age
counted from `fired_at_unix_ms`, the moment it fired. A reminder due at 09:00 that fires at 14:00
after a sleep reads as "just now" on the card.

Both schedule stores now keep the due time of a deliverable fire in
`ScheduledItem.deliverable_due_at`, set by `finish` from the claimed item's `due_at` before it moves
to the next occurrence, cleared with `deliverable_since`, and `None` on a record written before the
field existed. `DueReminder` in [proto/body.proto](../../../proto/body.proto) still has no due time,
so the card cannot show it.

Two more facts shape the card half. `BrainService` in `cortex_orchestrator/server.py` has neither the
display zone nor `CORTEX_SCHEDULE_POLL_S`: `list_due_reminders` gets only the store, so
`reminder_to_proto` cannot apply the late margin. And the overlay has no configured zone at all:
`Reminders.tsx` shows only `relativeTime(firedAtUnixMs)`, so a bare unix time would render in the
host's zone, which need not be the zone the toast names.

Reproduction ([readings](../../readings/overlay-idle-and-expiry-flows.md#the-brain-frozen-across-a-reply-and-a-reminders-due-time)):
set "Remind me in 90 seconds to check the oven." over `Converse`, then `docker pause` the brain
for 150 s and `docker unpause` it. The item's `due_at` was 03:29:34 UTC and its
`deliverable_since` 03:30:42, the thaw. On the Linux shell a new chat showed the card "Check the
oven", "2m ago", with no due time.

## What to do

1. Pass the schedule settings (zone and poll) to `BrainService` through `RpcPorts`, and split
   the margin test out of `late_phrase` so the toast and the card use one rule.
2. Add the due time to `DueReminder`, empty or 0 when the fire is on time or `deliverable_due_at`
   is `None`. Proposed, for a pick: a brain-rendered `due_label` (`due 08:00`, `due 21:00
   yesterday`, the words `late_phrase` writes), so the zone and the relative day stay in one
   place; the alternative is `due_at_unix_ms` plus the effective zone's IANA name, rendered with
   `Intl.DateTimeFormat`. The label's place on the card is a visual pick too.
3. Regenerate both stubs and the committed Rust stub, add the field to body core's `DueReminder`,
   the rpc mapping, the Tauri DTO, the TS type and the card, test every side, and run
   `just check-shell` with the library prefix in `~/.cache/cortex-linux-prefix/`.
4. Repeat the reproduction on the Linux shell.

## History

- 2026-10-26: filed from the idle and expiry flows on the `cortexn8` stack.
- 2026-10-26: both stores keep a deliverable fire's due time in `deliverable_due_at`.
- 2026-10-28: done. `DueReminder.due_label` is the brain's wording of a late reminder's due time,
  with `is_late_fire` split out of `late_phrase` and the ticker's zone and poll passed as
  `RpcPorts.reminder_view`; the card shows it as a tag on the meta line, in the existing
  `reminder-tag` style. The brain words the label and counts its day from the list (ADR-0066
  decision 11). On the Linux shell the frozen-brain reproduction showed `due 02:32`
  ([readings](../../readings/overlay-idle-and-expiry-flows.md#the-brain-frozen-across-a-reply-and-a-reminders-due-time)).
  A task's outcome has the same label, its lateness counted from its run's start, which both
  stores keep in `deliverable_started_at`.
