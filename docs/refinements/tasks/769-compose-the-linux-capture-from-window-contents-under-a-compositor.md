# Compose the Linux capture from window contents under a compositor

**Status:** open, optional feature
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-10-01

The X11 capture fails on a screen whose `_NET_WM_CM_S<screen>` selection has an owner. A compositing
manager paints the root from its own copy of each window, so a fade after a hide keeps the whole
overlay in the picture while the window tree lists it as unmapped, and its shadow lies outside the
overlay's rectangle ([x11-overlay-capture](../../readings/x11-overlay-capture.md)). GNOME's and
KDE's X11 sessions run one, so there capture is off.

Painting the body's unmapped windows for a time after a hide does not fix it. A fade lasts as long
as the compositor is set to, the shadow is outside every listed window, and an effect that scales
or moves a window, which some compositors have, can draw it outside its rectangle.

The fix reads no compositor output. Under the server grab, it lists the root's children in stacking
order and reads each viewable one with `GetImage` on the window itself, paints each bottom up at its
position inside the monitor, fills black where no window lies, since the root's own pixels are the
compositor's picture, and then paints the body's windows black as now. Under picom and xcompmgr a
window read this way returned its own pixels, with its covered parts intact; a frame returned its
client inside it; and a window unmapped 0.3 s earlier, still fading, returned `BadMatch` and was not
viewable ([x11-overlay-capture](../../readings/x11-overlay-capture.md)). The overlay window picom
paints is not among the root's children. So the composition holds no fade, shadow or other
compositor output. Three things the reads showed it must handle:

- **Clip each read to the screen.** A partly off-screen window read whole under a compositor and
  failed with `BadMatch` without one.
- **Read each window in its own format.** A depth-32 window read at depth 32 with an alpha channel,
  so the grab reads each window's depth and visual, and the core converts by that visual's masks
  and blends by alpha, or paints the window opaque.
- **A window the compositor does not redirect**, such as a full-screen one picom unredirects, is
  assumed to read as a window did with no compositor in the readings, its covered part black. The
  windows above it are painted over it, so that part does not reach the picture.

`RootGrab` gains a depth, a visual and an image per window, and the composition is covered core
code. Then a `composited` screen no longer fails the capture.

The check is the picom row of the readings with fading on: a capture in the fade, and one with the
overlay shown, each have no "other" pixel outside what the white window and the black fill give.

## History

- 2026-10-01: Filed when the X11 capture was checked under a window manager, two compositing
  managers and WebKit's compositing mode, and made to refuse a composited screen. Its per-window
  read was then checked under picom, xcompmgr and openbox, and holds.
