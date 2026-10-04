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
is the smaller path: `zbus` is already a dependency and `body_core` already has the `png` crate. A
live run on headless sway ([wayland-screenshot-portal](../../readings/wayland-screenshot-portal.md))
measured what the build rests on:

- **No dialog on sway.** The `xdg-desktop-portal` 1.18.4 frontend sends a non-interactive call
  through an `Access` backend's dialog only when the Screenshot backend reports `version` 2 or
  more and the app's `screenshot` permission is not `yes`. `xdg-desktop-portal-wlr` 0.7.1 reports
  1, so the call goes straight to it. A backend reporting 2 asks once, an unsandboxed app too, and
  stores the answer under app id `""` (read in the 1.18.4 source, not run).
- **What the desktop must have.** The frontend exports `Screenshot` only when some backend provides
  `org.freedesktop.impl.portal.Access` (gtk, gnome or kde), even though the wlr backend takes the
  picture. The wlr backend exits at startup without a PipeWire daemon, and captures by running
  `grim`: without it the call answers 2 with no results. The runbook must name all four.
- **The answer** is response 0 with `uri` `file:///tmp/out.png`, one fixed path every call
  overwrites, readable by other local users under a 002 umask. The core reads it right after the
  `Response`; whether the body then deletes it is the build's decision. The file is an 8-bit RGB
  PNG (colour type 2, no alpha) of the whole output, so the decode handles RGB as well as RGBA.
  The frontend can also answer 0 with no `uri`, which the core treats as a failure.
- **The handle** is `/org/freedesktop/portal/desktop/request/<sender>/<token>`: the caller's unique
  name without its `:` and with each `.` as `_`, then the `handle_token` option. It matched the
  returned path in every call, so the client subscribes to `Response` on it before calling.

Build it under [ADR-0011](../../adr/ADR-0011-body-v1.md) decision 13: the handle path, the
response codes 0, 1 and 2, the `uri` read and the PNG decode to BGRA in a covered core over a small
portal port, and a `zbus` adapter tested against a fake portal over a socket pair. The shell picks
the portal when `WAYLAND_DISPLAY` is set, and the overlay must still be kept out of the picture. The
X11 answer, [753](753-keep-the-overlay-out-of-a-linux-capture.md), finds the body's windows in the X
window tree, which a portal picture of a Wayland session does not come with, so it does not apply
there.

## History

- 2026-09-28: Filed when the Linux X11 capture backend was built under
  [263](263-linux-and-macos-capture-backends.md).
- 2026-10-01: Corrected. The entry named 753 as the overlay's exclusion here, but 753's fill reads
  window positions from the X tree, which a Wayland session's portal picture has no counterpart
  for. The shell still serves `DeniedScreenCapture` whenever `WAYLAND_DISPLAY` is set.
- 2026-10-04: Corrected after a live run. `sway` 1.9, `xdg-desktop-portal` 1.18.4,
  `xdg-desktop-portal-wlr` 0.7.1, `grim` and `pipewire`, extracted from the Ubuntu 24.04 archive
  into a userspace prefix, ran headless under `dbus-run-session` without sudo, and a
  non-interactive `Screenshot` call answered 0 with a PNG file URI and no dialog. The entry said
  most compositors show a dialog first; that is so only for a backend reporting version 2. The
  frontend also needs an `Access` backend, and the wlr backend a PipeWire daemon and `grim`.
  Readings in
  [wayland-screenshot-portal](../../readings/wayland-screenshot-portal.md).
