# The preference Tauri commands across a restart

**Status:** done 2026-10-06
**Session:** windows-desktop
**Capability:** W
**Origin:** [ADR-0032](../../adr/ADR-0032-preference-record.md)

The settings record crossed a real Tauri IPC hop on the Linux shell on 2026-10-06: the picked theme,
mark and window were written to the store, came back after a restart with no frame of the defaults,
and Auto cleared the theme and followed the system scheme both ways
([readings](../../readings/tauri-ipc-commands.md#the-commands-on-the-linux-shell)). Nothing in that
path is Windows code: `preferences.rs` and `brain.rs` have no `cfg` item, and the overlay's bridge
is one file for both shells. What WebView2 adds is the transport that every command shares with the
`converse` stream, which [H-001](001-bring-up-and-streamed-turn.md)'s streamed turn covers.

## History

- 2026-10-06: done on the Linux shell, with the system scheme switched by `GTK_THEME`
  ([readings](../../readings/tauri-ipc-commands.md#the-commands-on-the-linux-shell)). A brain down
  at launch showed the defaults, as the ADR's consequences say.
