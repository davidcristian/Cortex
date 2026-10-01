# Compose the Linux capture from window contents under a compositor

**Status:** open, optional feature
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-10-01

The X11 capture refuses a screen whose `_NET_WM_CM_S<screen>` selection has an owner. A compositing
manager paints the root from its own copy of each window, so a fade after a hide keeps the whole
overlay in the picture while the window tree lists it as unmapped, and its shadow lies outside the
overlay's rectangle ([x11-overlay-capture](../../readings/x11-overlay-capture.md)). GNOME's and
KDE's X11 sessions run one, so there capture is off.

Painting the body's unmapped windows for a time after a hide does not fix it. A fade lasts as long
as the compositor is set to, the shadow is outside every listed window, and an effect that scales
or moves a window, which some compositors have, can draw it outside its rectangle.

The fix reads no compositor output. Under the server grab, it lists the root's children in stacking
order and reads each viewable one that is not the body's with `GetImage` on the window itself,
which a redirected window is assumed to answer from its own pixmap (the first thing to check under
picom), then places each at its position, clipped by the windows above it and by the monitor, over
the root's background. `RootGrab` gains a request per window and the composition is covered core
code. Then `composited` stops refusing.

The check is the picom row of the readings with fading on: a capture in the fade, and one with the
overlay shown, each have no "other" pixel outside what the white window and the black fill give.

## History

- 2026-10-01: Filed when the X11 capture was checked under a window manager, two compositing
  managers and WebKit's compositing mode, and made to refuse a composited screen.
