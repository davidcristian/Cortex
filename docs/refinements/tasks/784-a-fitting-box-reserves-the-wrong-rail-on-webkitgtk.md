# A box that fits reserves the wrong rail on WebKitGTK

**Status:** open, blocked on host hardware
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md) decision 22
**Verified:** 2026-10-05

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

The proposed fix is `overflow-y: scroll` on the seven containers inside an
`@supports selector(::-webkit-scrollbar)` block, so an engine without the pseudo-element keeps
`auto`. `.field` has no `overflow-y` of its own, so the block names the seven as
`.stage :is(.history, .thoughts-body, .confirm-draft, .field, .rows, .switcher, .reminders)`, which
outranks each container's own rule. On WebKitGTK it reserves 6 px in both states and both GTK
modes and paints nothing in a fitting box's band, and on Chromium every probe page is pixel for
pixel unchanged ([scrollbar-gutter readings](../../readings/scrollbar-gutter.md)).

It changes one thing Chromium paints in the built overlay: in the demo view the reminder stack's
bottom border is drawn one row higher. The stack is 187.75 px tall at a fractional top. Under
`auto`, a stack that fits is painted for its rounded height from its rounded top, which puts the
border a row below the one nearest its layout edge. Under `scroll` it is painted on the nearest
row, as an overflowing stack already is under either rule
([readings](../../readings/scrollbar-gutter.md#where-chromium-paints-the-reminder-stacks-edges)).
So the row is the paint an overflowing stack gets today, and not a new condition to avoid.

It does not ship yet, because the engine the overlay ships on is WebView2 and nobody has read what
WebView2 paints under the rule: whether a fitting box shows a track or a disabled thumb in its
band, and whether anything moves beyond the stack's edge. That read needs the Windows shell and is
[H-789](../../host/tasks/789-what-webview2-paints-under-the-fenced-scroll-rule.md). When it passes,
the block above ships as written.

## History

- 2026-10-04: Filed when the gutter was read on WebKitGTK with the overlay's own stylesheet, and the
  6 px the padding assumes turned out to hold there only while a box overflows.
- 2026-10-04: The paint checks were run on WebKitGTK and on headed Chromium with the rule fenced to
  engines that have the pseudo-element. Both engines pass on probe pages, but the built overlay
  draws the reminder stack's bottom edge one row higher on Chromium, so the rule was not shipped.
- 2026-10-05: The demo view's row was read with the stack's layout beside it: Chromium paints a
  fitting stack under `scroll` the way it paints an overflowing one under either rule, each edge on
  the row nearest its layout edge. The remaining condition, the WebView2 read, was filed as
  [H-789](../../host/tasks/789-what-webview2-paints-under-the-fenced-scroll-rule.md).
