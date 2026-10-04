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

The proposed fix is `overflow-y: scroll` on the seven containers inside an
`@supports selector(::-webkit-scrollbar)` block, so an engine without the pseudo-element keeps
`auto`. `.field` has no `overflow-y` of its own, so the block names the seven as
`.stage :is(.history, .thoughts-body, .confirm-draft, .field, .rows, .switcher, .reminders)`, which
outranks each container's own rule. On WebKitGTK it reserves 6 px in both states and both GTK
modes and paints nothing in a fitting box's band, and on Chromium every probe page is pixel for
pixel unchanged ([scrollbar-gutter readings](../../readings/scrollbar-gutter.md)).

It does not ship yet, because it changes what Chromium paints in the built overlay: in the demo
view the reminder stack's bottom border is drawn one row higher, and setting `.reminders` alone
back to `auto` removes the difference. No probe page reproduces it. Before it ships:

- Find the condition in the overlay that makes Chromium draw that edge one row higher under
  `scroll`, by removing the stack's ancestors' rules one at a time in the demo view. Then either
  avoid it or show that it is the paint an overflowing stack already gets under `auto`.
- Read what WebView2 paints in a fitting and an overflowing box, which needs the Windows shell.

If the row cannot be avoided, one row on Chromium against a fitting box's band being 6 px too
narrow or 15 px too wide on WebKitGTK is a visual decision for the maintainer.

## History

- 2026-10-04: Filed when the gutter was read on WebKitGTK with the overlay's own stylesheet, and the
  6 px the padding assumes turned out to hold there only while a box overflows.
- 2026-10-04: The paint checks were run on WebKitGTK and on headed Chromium with the rule fenced to
  engines that have the pseudo-element. Both engines pass on probe pages, but the built overlay
  draws the reminder stack's bottom edge one row higher on Chromium, so the rule was not shipped.
