# Read a Wayland window through the ScreenCast portal

**Status:** open, optional feature
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-10-04

On a Wayland session the shell captures through the portal's `Screenshot`, whose picture is the
whole output with no window list, so `HiddenOverlayCapture` refuses every capture while the overlay
is shown and for 1 s after it hides ([body-os-linux](../../modules/body-os-linux.md)). The overlay
is shown for most of a turn, so a model's `capture_screen` is refused unless the user hid the
overlay first. A focus capture is `NoTarget` there as well.

`org.freedesktop.portal.ScreenCast` with a window source streams one window's own buffer over
PipeWire, which a compositor renders without the windows above it, so the overlay cannot be in it.
The user picks the window in a dialog, and `persist_mode` with a restore token can keep that choice
across calls. That could serve the focus target while the overlay is open. It needs a PipeWire
client and a backend that offers window sources. Whether `xdg-desktop-portal-wlr` 0.7.1 on sway
1.9 offers one is not read yet: the portal's `AvailableSourceTypes` property on the headless sway
stack answers it.

## History

- 2026-10-04: Filed when the shell started serving the portal capture under
  [752](752-wayland-screen-capture-through-the-portal.md) with the overlay refusal.
