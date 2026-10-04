# Read the root background under a compositing manager

**Status:** done 2026-10-02
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Under a compositing manager the Linux capture paints each viewable top-level window read on its own
over black ([body-os-linux](../../modules/body-os-linux.md)), so where no window lies the picture is black. A
desktop environment usually maps a full-screen desktop window, which is read like any other, so the
black shows only on a bare window manager. There picom and xcompmgr paint the pixmap that a setter
such as feh names in the root's `_XROOTPMAP_ID`; with no such property picom paints black and
xcompmgr gray, and `xsetroot -solid` writes none
([x11-overlay-capture](../../readings/x11-overlay-capture.md)). `X11Root` also still reads the
root's own pixels on such a screen, and the core then discards them, one extra `GetImage` of the
monitor per capture.

The change, in `X11Root::grab`:

- **Skip the root read when the selection has an owner.** Ask for the owner before reading the
  root, and return either the root's image or the layers, so the snapshot holds one or the other.
  This moves the root's `GetImage` after the window list, which renumbers every scripted reply in
  the `x11` test suite.
- **Read the background as the bottom layer.** Read `_XROOTPMAP_ID` as a `PIXMAP`. When it names a
  pixmap at the root's depth, read with `GetImage` the part of it inside both the monitor and the
  pixmap, from the root's origin and not tiled, as picom paints it. A read must lie wholly inside
  the pixmap, or it fails with `BadMatch`.
- **Describe that read by the root visual.** A pixmap's `GetImage` reply names visual 0, so
  `picture` would find no masks and `to_bgra` would fail the whole capture.
- **Leave the base black otherwise**: no property, a pixmap of another depth, or a pixmap the server
  no longer has, which `GetGeometry` reports as an error. None of these fails the capture.

xcompmgr tiles a pixmap smaller than the screen and paints gray where there is none, so under it
those parts of the capture still differ from the screen.

The check is a capture under picom with a screen-sized background pixmap and no desktop window,
whose pixels outside every window match the pixmap, with no shadow pixel.

## History

- 2026-10-01: Filed when the capture under a compositing manager was built from window reads over
  black.
- 2026-10-02: Checked on `Xvfb` under picom and xcompmgr: `xsetroot` writes no property, picom
  paints a small pixmap once rather than tiled, and a pixmap read names no visual, so the plan above
  names the property's writers, the origin rule, the root visual and the fallbacks. Built to it:
  the grab asks for the selection's owner before any pixel read and returns `Pixels::Root` or
  `Pixels::Layers`, the background pixmap is the bottom layer, `x11.rs` is split into the grab,
  `x11/tree.rs` and `x11/pixels.rs`, and the `x11` suite's fake server numbers each reply itself.
  Under picom with a screen-sized pixmap the capture matched it on all 864,000 pixels outside the
  windows, with no shadow pixel, against 864,000 black before
  ([x11-overlay-capture](../../readings/x11-overlay-capture.md)). Closed.
