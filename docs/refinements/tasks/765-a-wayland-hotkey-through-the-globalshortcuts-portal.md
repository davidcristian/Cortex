# A Wayland hotkey through the GlobalShortcuts portal

**Status:** open, optional feature
**Area:** cross-cutting
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)
**Verified:** 2026-10-01

The Linux `Hotkey` backend grabs a key on an X server's root window, so a Wayland session gets no
global hotkey from it. With no `DISPLAY`, `x11rb::connect(None)` fails and `X11Keys::absent` makes
every registration fail as `Registration`. With Xwayland the grab succeeds, but Xwayland receives a
key only while one of its own windows has focus, so the chord fires only over X windows. That second
case is an assumption from how Xwayland routes input: the live test reached WSLg's Xwayland through
XTEST, which injects into the X server itself and so does not test it.

A Wayland compositor gives a client a global shortcut only through the XDG desktop portal's
`org.freedesktop.portal.GlobalShortcuts`: `CreateSession`, then `BindShortcuts` with one shortcut
id, a description and a preferred trigger, answered in the `Response` signal of a request object,
then an `Activated` signal on each press. The compositor may ask the user to confirm or change the
trigger, so the chord the user sees can differ from `CORTEX_HOTKEY`; the runbook would say so.
`zbus` is already a dependency. Build it under [ADR-0011](../../adr/ADR-0011-body-v1.md) decision
13: the session and bind requests, the trigger text a chord becomes and the response codes in a
covered core over a small portal port, and a `zbus` adapter tested against a fake portal over a
socket pair. The shell picks the portal when `WAYLAND_DISPLAY` is set, which is
[766](766-register-the-linux-hotkey-in-the-shell.md). The portal side shares its request and
response handling with the screenshot portal in
[752](752-wayland-screen-capture-through-the-portal.md).

## History

- 2026-10-01: Filed when the X11 hotkey backend was built under
  [271](271-macos-linux-os-backends.md).
