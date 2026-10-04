# A Wayland hotkey through the GlobalShortcuts portal

**Status:** done 2026-10-04
**Area:** cross-cutting
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)

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
socket pair. The shell's Linux `hotkey::register` grabs nothing and logs why when `WAYLAND_DISPLAY`
is set and not empty, and that branch is where it would open the portal instead. The portal side
shares its request and response handling with the screenshot portal in
[752](752-wayland-screen-capture-through-the-portal.md).

## History

- 2026-10-01: Filed when the X11 hotkey backend was built under
  [271](271-macos-linux-os-backends.md).
- 2026-10-04: Checked which portal backends serve `GlobalShortcuts` on this host's Ubuntu 24.04
  archive. The `xdg-desktop-portal` 1.18.4 frontend has the interface. Of the backends, only
  `xdg-desktop-portal-kde` 5.27.11 lists `org.freedesktop.impl.portal.GlobalShortcuts` in its
  portal file; `xdg-desktop-portal-wlr` 0.7.1 lists `Screenshot` and `ScreenCast` only,
  `xdg-desktop-portal-gnome` 46.2 does not list it, and no Hyprland backend is packaged. A live test
  here would need a KDE Wayland session (`kwin_wayland` with `kglobalaccel`) and was not tried. The
  covered core and a `zbus` adapter tested against a fake portal over a socket pair can be built
  and checked here, and share their request handling with
  [752](752-wayland-screen-capture-through-the-portal.md).
- 2026-10-04: Done for the backend. The premise held: the port needs a press and a registration
  error, both of which the portal gives, and the screenshot adapter's request exchange moved into
  a shared module with its tests unchanged. `LinuxPortalHotkey` creates one session per chord and
  binds one shortcut in it; `DbusShortcuts` makes the calls; the hotkey check list runs over the
  core, and the adapter is tested against a fake portal over a socket pair
  ([body-os-linux](../../modules/body-os-linux.md)). No live test, since no backend here serves the
  interface. The shell wiring, which needs its own thread because a bind may wait on a user dialog,
  is [788](788-wire-the-portal-hotkey-into-the-wayland-shell.md).
