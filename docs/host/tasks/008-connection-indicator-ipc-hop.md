# The connection indicator's real IPC hop

**Status:** done 2026-10-06
**Session:** windows-desktop
**Capability:** W
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)

`check_link` crossed a real Tauri IPC hop on the Linux shell on 2026-10-06: green with the brain up,
red on a summon with it stopped and re-checked every 5 s, green on its own once it was back, and
amber with a wrong token
([readings](../../readings/tauri-ipc-commands.md#the-commands-on-the-linux-shell)). Nothing in that
path is Windows code: `link.rs` and `brain.rs` have no `cfg` item, and the overlay's bridge is one
file for both shells. What WebView2 adds is the transport that every command shares with the
`converse` stream, which [H-001](001-bring-up-and-streamed-turn.md)'s streamed turn covers.

## History

- 2026-10-06: done on the Linux shell, the brain stopped and started with `docker compose`
  ([readings](../../readings/tauri-ipc-commands.md#the-commands-on-the-linux-shell)). The runbook
  said the chat list fills in when the dot turns green; nothing refreshes the list on recovery, as
  ADR-0021 decision 8 states, and the runbook now says so.
