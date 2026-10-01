# The shell has never been run on Linux

**Status:** open, optional feature
**Area:** body-gateway
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)
**Verified:** 2026-10-01

The shell's Linux `start` in `body/app/src-tauri/src/body_server.rs` serves `LinuxAudioControl`
and `LinuxNotify` over the session bus, with `DeniedScreenCapture`, and its Linux
`hotkey::register` grabs the chord on the X display. `just check-shell` type-checks both, and the
same `start` composition, run outside Tauri, served a reminder and a volume change over gRPC
against a real session bus and sound server. No Linux build has run the shell, so the Tauri half of
that path is unproven there: `start` opening the session bus during Tauri's setup, the server task
on Tauri's runtime, and the hotkey's listener thread toggling the overlay from outside the main
thread.

A Linux build links on a box without sudo from the userspace prefix the
[shell clippy readings](../../readings/shell-clippy.md) describe, and runs with that prefix on
`LD_LIBRARY_PATH`. Run `npm run tauri dev` in `body/app` on a Linux desktop session with a
notification server and `pactl` on `PATH`, point a brain at `CORTEX_BODY_ADDR`, and check that a
fired reminder shows, that `set_volume` changes the default sink, and that the chord toggles the
overlay on an X11 session.

## History

- 2026-09-28: Filed when the shell's Linux `start` was wired to the `os_linux` backends under
  [271](271-macos-linux-os-backends.md). Outside Tauri, the composition showed a reminder on
  `dunst` 1.9.2, set and restored the volume on a PulseAudio 17.0 server, answered
  `PermissionDenied` to a capture, and with no session bus answered `FailedPrecondition` to
  `Notify` while volume still worked.
- 2026-10-01: The shell's Linux `hotkey::register` was wired to `LinuxHotkey`, which adds the
  hotkey to what a run checks. `cargo build --locked` linked the shell on this host from the
  userspace prefix in the [shell clippy readings](../../readings/shell-clippy.md); it was not run.
