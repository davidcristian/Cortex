# A failed body server bind is shown nowhere

**Status:** open, waiting for its trigger
**Area:** body-gateway
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md) decision 6
**Trigger:** a History line in this file recording the maintainer's pick of A, B or C.
**Verified:** 2026-10-07

When the shell cannot bind `CORTEX_BODY_ADDR`, `serve` in `body/app/src-tauri/src/body_server.rs`
prints `cortex: could not bind BodyService on <addr>: <error>` to standard error and returns, and
the shell runs on without a body server. A Windows release build has no console
(`windows_subsystem = "windows"` in `main.rs`), so there the line goes nowhere. The brain's body
tools then answer `UNREACHABLE` at their first call, which tells the user the body is missing but
not why. On 2026-10-06, 23 runs of the Linux shell printed that line for `127.0.0.1:50151`, a port
inside a range the Windows host had reserved
([port reservations](../../readings/windows-port-reservations.md)), and nothing else reported it.

ADR-0023 decision 6 keeps the shell running, since the conversation does not need `BodyService`,
and says the failure is to be shown to the user. Where it shows is a visual pick.

## Proposal

- **A. A notification at startup** (recommended). `serve` already holds the body's `Notify`
  backend when the bind fails, so it sends one notification naming the address, the error and
  `CORTEX_BODY_ADDR`: a toast on Windows, a freedesktop notification on Linux. It appears once,
  when the user is starting the app. On Windows it shows only once the toast's app id is
  registered ([H-003](../../host/tasks/003-real-reminder-toast.md)).
- **B. The tray.** The tray's tooltip, or a disabled menu line, says the body server is off and
  why. It stays readable for the whole run, but only a user who opens the tray sees it, and a
  Linux tray host shows no tooltip, since the item exports none
  ([readings](../../readings/tauri-ipc-commands.md#the-tray-menu-on-the-linux-shell)).
- **C. The overlay.** The shell emits an event and the panel shows a line, or the link dot takes
  a state for it. It is the most visible, and needs a Tauri event, an overlay port, its component
  and Vitest coverage.

The sentence itself belongs in `body_core` or `body_rpc` as a pure function, so `just check`
covers its wording, with the shell only calling it.

## History

- 2026-10-07: filed when both default ports moved below Windows' dynamic port range; the surface
  is a visual pick, so it waits for the maintainer.
