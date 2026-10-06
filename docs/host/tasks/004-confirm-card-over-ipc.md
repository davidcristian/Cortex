# The confirm card through real Tauri IPC

**Status:** done 2026-10-06
**Session:** windows-desktop
**Capability:** W
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

The card's answer reached live turns through a real Tauri IPC hop on the Linux shell on 2026-10-06:
Approve ran the action that needed approval and the turn went on, Deny returned the refusal with
nothing done, and a card left alone while the overlay was minimized kept its preview up until the
brain denied on its timeout
([readings](../../readings/tauri-ipc-commands.md#the-commands-on-the-linux-shell)). Nothing in that
path is Windows code: `confirm.rs` and `converse.rs` have no `cfg` item, and the overlay's bridge is
one file for both shells. What WebView2 adds is the transport that every command shares with the
`converse` stream, which [H-001](001-bring-up-and-streamed-turn.md)'s streamed turn covers.

## History

- 2026-07-19: moved here from the refinements backlog, where the Windows-native validation of the
  card had been a counted entry in the untrusted-content area. A dated pointer stays at the origin
  doc so the trail from an ADR through that backlog still resolves.
- 2026-10-06: done on the Linux shell against the cortex on the card, `schedule_task` needing
  approval and every click sent by `xdotool`
  ([readings](../../readings/tauri-ipc-commands.md#the-commands-on-the-linux-shell)). The run filed
  [R-797](../../refinements/tasks/797-the-hotkey-hides-the-window-without-telling-the-overlay.md), a
  hotkey press during a turn hiding the window so that a card raised after it times out unseen.
