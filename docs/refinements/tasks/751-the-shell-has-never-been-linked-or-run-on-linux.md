# The shell has never been linked or run on Linux

**Status:** open, optional feature
**Area:** body-gateway
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)
**Verified:** 2026-09-28

The shell's Linux `start` in `body/app/src-tauri/src/body_server.rs` serves `LinuxAudioControl`
and `LinuxNotify` over the session bus, with `DeniedScreenCapture`. `just check-shell` type-checks
it, and the same composition, run outside Tauri, served a reminder and a volume change over gRPC
against a real session bus and sound server. No Linux build has linked the shell or run it, so the
Tauri half of that path is unproven there: `start` opening the session bus during Tauri's setup,
and the server task on Tauri's runtime.

Linking needs the GTK, webkit and dbus stack that the CI `shell` job installs as five `-dev`
roots, and running needs their runtime libraries. On a box without them and without sudo, both come
from a userspace prefix built with `apt-get download` and `dpkg-deb -x`, as the
[shell clippy readings](../../readings/shell-clippy.md) describe for the clippy run. Then run
`npm run tauri dev` in `body/app` on a Linux desktop session with a notification server and `pactl`
on `PATH`, point a brain at `CORTEX_BODY_ADDR`, and check that a fired reminder shows and that
`set_volume` changes the default sink.

## History

- 2026-09-28: Filed when the shell's Linux `start` was wired to the `os_linux` backends under
  [271](271-macos-linux-os-backends.md). Outside Tauri, the composition showed a reminder on
  `dunst` 1.9.2, set and restored the volume on a PulseAudio 17.0 server, answered
  `PermissionDenied` to a capture, and with no session bus answered `FailedPrecondition` to
  `Notify` while volume still worked.
