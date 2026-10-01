# The overlay panel does not open in the Linux webview

**Status:** open, optional feature
**Area:** body-overlay
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)
**Verified:** 2026-10-01

A debug build of the shell, run on Linux under `Xvfb` as the
[overlay runbook](../../runbooks/body-overlay.md) describes, loads the overlay from `devUrl`
(`http://localhost:5173`, here a static server of `body/app/dist`) into WebKitGTK 2.52.6. The page
renders the stage and the theme toggle, and each hotkey press shows or hides the window, but the
panel never opens: not on the first press, which shows the window while the page loads, not after
a hide and a show eight seconds after the load, and not with `WEBKIT_DISABLE_COMPOSITING_MODE=1`.
No brain was reachable at `CORTEX_BRAIN_ADDR`.

`toggle_overlay` emits `cortex:activate` after `show`, and `main.tsx` forwards it to the DOM event
`App` opens the panel on, through `listen` from `@tauri-apps/api/event`. Three causes are not yet
separated: `listen` failing over WebKitGTK's IPC, so the event never reaches the page; the
panel opening but not painting under `Xvfb`, where EGL has no DRI3 device; and the panel waiting
on a brain that does not answer. Log the `listen` promise's result and the controller's mode to
the console, read them through the WebKit inspector or stderr, and run once with a brain answering
`CORTEX_BRAIN_ADDR`.

## History

- 2026-10-01: Filed when the shell first ran on Linux under
  [751](751-the-shell-has-never-been-linked-or-run-on-linux.md).
