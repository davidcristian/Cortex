# A box that fits reserves the wrong rail on WebKitGTK

**Status:** open, actionable
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md) decision 22
**Verified:** 2026-10-04

Every scroll container in `body/app/src/overlay.css` has `overflow-y: auto` and
`scrollbar-gutter: stable`, and takes the reserved band out of its inline-end padding on the
assumption that the band is `--rail`, 6 px. On WebKitGTK 2.52.6, the engine the Linux shell renders
through, that holds only while a box overflows. A box that fits reserves the GTK theme's own band:
none with GTK's overlay scrolling, which is GTK's default, and 21 px with it off
([scrollbar-gutter readings](../../readings/scrollbar-gutter.md)). Chromium reserves 6 px in both
states.

So on the Linux shell, with overlay scrolling, a box that fits ends one rail short of its intended
inset (a `.history` bubble ends 10 px from the panel edge rather than 16), and its content gets
6 px narrower the moment it starts to scroll. That is the reflow `scrollbar-gutter: stable` is there
to prevent, for instance a draft re-wrapping in `.field` when it reaches the 120 px cap. With
overlay scrolling off, the box is 15 px wider than intended while it fits.

The measured-width probe [146](146-reserved-rail-assumed-width.md) proposes does not fix this. The
band depends on the box's state, not only on the engine, so one reading at startup is wrong in one
of the two states.

The proposed fix is `overflow-y: scroll` in place of `auto` on the seven containers. In the same
readings it reserves 6 px in both states on Chromium and on WebKitGTK in both GTK modes, so the
existing subtraction balances wherever `::-webkit-scrollbar` exists. Before it ships, three things
need a reading:

- What WebKitGTK paints in a fitting `textarea.field` under `scroll`: the readings record found 17
  black pixels in the band's bottom corner there, and nothing in a fitting `div`.
- What Chromium and WebView2 paint in a fitting box under `scroll`. A headed screenshot is needed,
  since the headless shell drew no thumb at all.
- What `scroll` does on an engine without the pseudo-element, where an empty track may show. If it
  shows one, the change goes inside an `@supports selector(::-webkit-scrollbar)` block.

## History

- 2026-10-04: Filed when the gutter was read on WebKitGTK with the overlay's own stylesheet, and the
  6 px the padding assumes turned out to hold there only while a box overflows.
