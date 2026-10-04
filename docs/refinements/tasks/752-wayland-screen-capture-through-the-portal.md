# Wayland screen capture through the desktop portal

**Status:** open, optional feature
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-10-04

The Linux capture backend reads an X server's root window, so a Wayland session gets no picture
from it. With no `DISPLAY`, `x11rb::connect(None)` fails and `X11Root::absent` makes every capture
`NoDisplay`. With rootless Xwayland the connection opens, but `GetImage` on the root answers
`BadMatch`, which the backend reports as `Backend`: measured on WSLg's Xwayland on 2026-09-28.
Either way no wrong picture is sent, and no picture is sent at all.

A Wayland compositor gives a client the screen only through the XDG desktop portal:
`org.freedesktop.portal.Screenshot`, which returns a PNG file URI in the `Response` signal of a
request object, or `org.freedesktop.portal.ScreenCast`, which returns a PipeWire stream. Screenshot
is the smaller path: `zbus` is already a dependency and `body_core` already has the `png` crate.
Most compositors show a permission dialog before the first screenshot, which the runbook would
name. Build it under [ADR-0011](../../adr/ADR-0011-body-v1.md) decision 13: the request, the
response codes and the PNG decode to BGRA in a covered core over a small portal port, and a `zbus`
adapter tested against a fake portal over a socket pair. The shell picks the portal when
`WAYLAND_DISPLAY` is set, and the overlay must still be kept out of the picture. The X11 answer,
[753](753-keep-the-overlay-out-of-a-linux-capture.md), finds the body's windows in the X window
tree, which a portal picture of a Wayland session does not come with, so it does not apply there.

## History

- 2026-09-28: Filed when the Linux X11 capture backend was built under
  [263](263-linux-and-macos-capture-backends.md).
- 2026-10-01: Corrected. The entry named 753 as the overlay's exclusion here, but 753's fill reads
  window positions from the X tree, which a Wayland session's portal picture has no counterpart
  for. The shell still serves `DeniedScreenCapture` whenever `WAYLAND_DISPLAY` is set.
- 2026-10-04: Checked whether a portal stack can run on this host without sudo. The Ubuntu 24.04
  archive has `xdg-desktop-portal` 1.18.4, `xdg-desktop-portal-wlr` 0.7.1, whose portal file lists
  `Screenshot` and `ScreenCast` with `UseIn=wlroots;sway`, and `sway` 1.9, which runs headless with
  `WLR_BACKENDS=headless`. `apt-cache depends --recurse` lists 275 packages for `sway` and the wlr
  backend, many already installed, so a userspace extraction like the one that ran `twm` under
  [263](263-linux-and-macos-capture-backends.md) is the next live step, under `dbus-run-session`
  with `XDG_CURRENT_DESKTOP=sway`. It was not run. The covered core and a `zbus` adapter tested
  against a fake portal over a socket pair, as `DbusNotifications` is, need none of that and are the
  first step.
