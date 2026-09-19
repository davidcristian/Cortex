# The liquid edge's backdrop blur

**Status:** open, optional feature
**Area:** body-overlay
**Origin:** [ADR-0036](../../adr/ADR-0036-window-edge.md)
**Trigger:** The transparent-window pass, when the desktop shows through and a Still panel is frosted while a liquid one is merely translucent.
**Verified:** 2026-09-19

Chromium composites `backdrop-filter` output without clipping it by a `path()` clip, so a sculpted
panel showed a sharp frosted rectangle behind the liquid outline. What shipped instead paints
`--panel-solid`, a near-opaque theme colour, on the clipped shape. That costs nothing today because
the v1 window is opaque, so there is nothing behind the glass to blur. It matters once the window
becomes transparent and the desktop shows through.

Two fixes were seen working in the design pitch: a `mask-image` built from the same outline (masks
do clip `backdrop-filter` output), or retesting the clip path once WebView2's Chromium fixes the
compositing. Measure again first, since the engine changes.

## History

- 2026-08-07: Found by reading the area's entries against the header that counts them. It had been
  open since 2026-07-21 without appearing in any published count, because the area header and the
  table cell were each written from the other.
- 2026-08-09: A costing pass left it as written. Measure again first, then cost the `mask-image`
  option.
- 2026-09-13: Checked again; the premise holds. The stylesheet comment named only the host window
  task and said nothing about the blur trade, so it now names this file as well.
- 2026-09-19: Checked again; nothing in the overlay has changed. `backdrop-filter: none` on
  `.panel.edge-live` is at `body/app/src/overlay.css` line 308, the unclipped `.panel` keeps
  `blur(30px) saturate(140%)` at line 276, and the measurement is at lines 300 to 302. The trigger
  has not fired: host task 014 is still never attempted and the shell's window is still
  `"transparent": false` in `body/app/src-tauri/tauri.conf.json`.
