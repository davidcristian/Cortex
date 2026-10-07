# The tray's Show overlay entry hides a shown overlay

**Status:** open, waiting for its trigger
**Area:** body-overlay
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md) decision 5
**Trigger:** a History line in this file recording the maintainer's pick of A, B or C.
**Verified:** 2026-10-07

The tray menu's first entry reads `Show overlay`, and `body/app/src-tauri/src/tray.rs` sends it to
`toggle_overlay` in `lib.rs`, the function the hotkey calls. On a hidden window that shows the
overlay. On a shown one it sends `cortex:toggle`, and the overlay hides its panel or opens its orb
or preview, by its mode. On 2026-10-07 the entry, sent through `com.canonical.dbusmenu` on the
Linux shell, hid the shown window
([readings](../../readings/tauri-ipc-commands.md#the-tray-menu-on-the-linux-shell)). The
[runbook](../../runbooks/body-overlay.md) describes the entry as doing what the hotkey does, so the
code matches the docs and only the label reads otherwise. Which of the two changes is a pick.

## Proposal

- **A. Show only** (recommended). The entry shows and focuses the window and sends
  `cortex:activate` whether or not the window is shown, so it does what its label says and a second
  click changes nothing. Hiding stays with the hotkey and Escape. It needs a `show_overlay` beside
  `toggle_overlay` in `lib.rs`, and the runbook's first validation step changed.
- **B. A label for the toggle**, such as `Show or hide overlay`. Only the string changes, but the
  label is longer, and a tray entry that hides the window it names is unusual.
- **C. A label that follows the window**: `Show overlay` while hidden and `Hide overlay` while
  shown, set with `MenuItem::set_text` on each show and hide. It names what the click does next,
  and needs the shell to keep the menu item and update it from `toggle_overlay` and
  `set_overlay_shown`.

## History

- 2026-10-07: filed from [H-001](../../host/tasks/001-bring-up-and-streamed-turn.md) when the
  tray menu ran on the Linux shell under a StatusNotifier host written for the run.
