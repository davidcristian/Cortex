# The session-read Tauri commands

**Status:** done 2026-10-06
**Session:** windows-desktop
**Capability:** W
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-rpcs.md)

The two reads crossed a real Tauri IPC hop on the Linux shell on 2026-10-06: the switcher listed the
chats in the store's order with their titles and previews, the cycle keys loaded each chat's
history, and a restart came back to the most recently active chat
([readings](../../readings/tauri-ipc-commands.md#the-commands-on-the-linux-shell)). Nothing in that
path is Windows code: `sessions.rs` and `brain.rs` have no `cfg` item, and the overlay's bridge is
one file for both shells. What WebView2 adds is the transport that every command shares with the
`converse` stream, which [H-001](001-bring-up-and-streamed-turn.md)'s streamed turn covers.

## History

- 2026-10-06: done on the Linux shell against five chats in a fresh store, every key sent by
  `xdotool` ([readings](../../readings/tauri-ipc-commands.md#the-commands-on-the-linux-shell)).
