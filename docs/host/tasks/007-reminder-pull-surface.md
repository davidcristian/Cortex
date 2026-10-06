# The reminder pull surface on the hotkey path

**Status:** done 2026-10-06
**Session:** windows-desktop
**Capability:** W
**Origin:** [ADR-0066](../../adr/ADR-0066-reminder-toast-and-card.md)

The card stack read correctly at the real 640 by 720 window on the Linux shell on 2026-10-06, with
reminders the cortex had scheduled and fired: each card had its text and its age, `repeats` on the
series and the dashed, red-tinted `untrusted source` badge on the reminder set from a turn holding a
picture. Dismissing a card acked its fire, and with the brain's container stopped a summon turned
the dot red and left the cards in place
([readings](../../readings/tauri-ipc-commands.md#attached-pictures-and-reminder-cards)). Nothing in
that path is Windows code: `reminders.rs` has no `cfg` item, and the pull runs on the summon that
both shells raise through `cortex:activate`. What Windows adds is the `os_windows` hotkey and
WebView2's transport and paint, which [H-001](001-bring-up-and-streamed-turn.md)'s bring-up and
streamed turn cover.

## Notes

- It pairs with the reminder toast check, [H-003](003-real-reminder-toast.md), which stays: the
  push half is the Windows toast backend.

## History

- 2026-07-19: given a backlog line, though it was never unrecorded:
  [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)'s host line has named the overlay's
  reminder surface on the real hotkey path since the slice was added, and the procedure is in the
  runbook.
- 2026-10-06: done on the Linux shell against the cortex on the card, with every key from
  `xdotool`. The run found that the stack opens only on a chat with no messages, so a summon over
  the chat that set the reminders showed no card
  ([R-803](../../refinements/tasks/803-a-summon-over-a-chat-with-messages-shows-no-due-reminder.md)).
