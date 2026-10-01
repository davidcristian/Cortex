# Read the root background under a compositing manager

**Status:** open, optional feature
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-10-01

Under a compositing manager the Linux capture paints each viewable top-level window read on its own
over black ([body-os](../../modules/body-os.md)), so where no window lies the picture is black
rather than the desktop background a user sees. A desktop environment usually maps a full-screen
desktop window, which is read like any other, so the black shows only on a bare window manager.
`X11Root` also still reads the root's own pixels on such a screen, and the core then discards them,
one extra `GetImage` of the monitor per capture.

The change: when the selection has an owner, read the pixmap the root's `_XROOTPMAP_ID` property
names, the background that setters such as `feh` and `xsetroot` write and compositing managers
paint, as the base under the windows, and skip the root's own read. With no such property the base
stays black. The check is a capture under picom with a background set and no desktop window, whose
pixels outside every window match the background.

## History

- 2026-10-01: Filed when the capture under a compositing manager was built from window reads over
  black.
