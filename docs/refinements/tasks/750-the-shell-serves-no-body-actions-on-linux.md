# The shell serves no body actions on Linux

**Status:** open, optional feature
**Area:** body-gateway
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)
**Verified:** 2026-09-28

`os_linux` has real `Notify` and `AudioControl` backends, and nothing starts them. The Tauri shell's
`body_server::start` is `#[cfg(windows)]`, and its `#[cfg(not(windows))]` twin only prints that the
body server is not available, so on Linux the brain's `notify` and volume calls reach no
`BodyService` at all.

The wiring is host code in `body/app/src-tauri/src/body_server.rs`, outside the checked workspace
(ADR-0011 decisions 5 and 13):

- open the session bus with `os_linux::zbus::blocking::Connection::session()` and build
  `LinuxNotify::new(app_name, DbusNotifications::new(connection))`. `LinuxNotify` needs an open
  connection, so a session with no bus needs a decision: the server should still serve volume, and
  `notify` should report `NotifyError::Unavailable`, for example through a `NotificationBus` that
  always fails, written and covered in `os_linux`;
- build `LinuxAudioControl::new(PactlCommand::new(PACTL_PROGRAM))`;
- serve them with `DeniedScreenCapture` until a Linux capture backend exists
  ([263](263-linux-and-macos-capture-backends.md));
- add `os-linux` to the shell's manifest under a `cfg(target_os = "linux")` target table.

`just check-shell` clippies the shell for the host target, which is where this code would be
type-checked. A run on a Linux desktop then checks a reminder toast and a volume change end to end.

## History

- 2026-09-28: Filed when the Linux `Notify` and `AudioControl` backends were built under
  [271](271-macos-linux-os-backends.md), whose live tests reach the session bus and the sound server
  directly rather than through the shell.
