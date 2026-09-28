# Wayland screen capture through the desktop portal

**Status:** open, optional feature
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-28

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
`WAYLAND_DISPLAY` is set, and the overlay must still be kept out of the picture, which is
[753](753-keep-the-overlay-out-of-a-linux-capture.md).

## History

- 2026-09-28: Filed when the Linux X11 capture backend was built under
  [263](263-linux-and-macos-capture-backends.md).
