# Register the Linux hotkey in the shell

**Status:** open, optional feature
**Area:** cross-cutting
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)
**Verified:** 2026-10-01

`os_linux` has a working X11 `LinuxHotkey`, but the shell's `hotkey::register` in
`body/app/src-tauri/src/hotkey.rs` is a stub off Windows that prints that the hotkey is not
implemented, and `configured_chord` is `cfg(windows)`. The Linux form opens the display with
`os_linux::x11rb::connect(None)`, wraps it in `X11Keys::new`, or `X11Keys::absent` with the error
when it fails, registers the configured chord on `LinuxHotkey::new` with the same
`toggle_overlay` callback, and keeps the backend for the whole run as the Windows form does.
`configured_chord` then takes `cfg(any(windows, target_os = "linux"))`.

On a Wayland session the shell picks the portal instead
([765](765-a-wayland-hotkey-through-the-globalshortcuts-portal.md)).
`just check-shell` type-checks the change, which needs the userspace prefix the
[shell clippy readings](../../readings/shell-clippy.md) describe and a resource compiler for the
Windows target, neither of which this host had on 2026-10-01. Running it is
[751](751-the-shell-has-never-been-linked-or-run-on-linux.md).

## History

- 2026-10-01: Filed when the X11 hotkey backend was built under
  [271](271-macos-linux-os-backends.md).
