# The liquid edge's backdrop blur

**Status:** open, feature breadth
**Area:** body-overlay
**Origin:** [ADR-0036](../../adr/ADR-0036-window-edge.md)
**Trigger:** The transparent-window pass, when the desktop shows through and a Still panel is frosted while a liquid one is merely translucent.
**Verified:** 2026-09-13

Measured in the design pitch that chose it
and pinned in ADR-0036: Chromium composites `backdrop-filter` output without clipping it by a
`path()` clip, so a sculpted panel showed a sharp frosted rectangle ghosting behind the liquid
outline. The shipped trade paints `--panel-solid` (a near-opaque theme token) on the clipped
slab instead, which costs nothing visible today: the v1 window's ground behind the panel is
opaque, so there is nothing behind the glass to blur. It becomes real at the transparent-window
pass, when the desktop shows through and a Still panel is frosted while a liquid one is merely
translucent. Two fix shapes were seen working in that same pitch: a `mask-image` built from the
same outline (masks DO clip backdrop-filter output, the corner-dissolve candidate proved it), or
re-testing the clip path once WebView2's Chromium fixes the compositing. Whoever picks this up
should start by re-measuring, since the engine moves. Placed here 2026-07-21.

## Trail

- 2026-08-07: Found by reading the area's entries against the header that counts them rather than by
  counting, having been open since 2026-07-21 and carried in the index's running record under this
  same area the whole time while no count either doc published had ever named it. There was no
  compensating error hiding it: the area header and the table cell simply agreed on a number that
  had never included it, and each of those two summaries was written from the other, so their
  agreement established nothing.
- 2026-08-09: A costing pass over the feature-breadth bucket re-read it and left it parked exactly
  as written. The measurement it rests on is still the one in the sheet, `body/app/src/overlay.css`
  lines 297 to 299 recording that Chromium does not clip `backdrop-filter` output by a `path()`
  clip, with line 304 setting `backdrop-filter: none` on `.panel.edge-live` while the unclipped
  `.panel` at line 273 keeps its `blur(30px) saturate(140%)`. Re-measure first, as the entry says,
  and only then cost the `mask-image` candidate.
- 2026-09-13: Re-derived and the premise holds, with two pointers refreshed. The measurement now
  sits at `body/app/src/overlay.css` lines 300 to 303, `backdrop-filter: none` on `.panel.edge-live`
  at line 307, and the unclipped `.panel` keeps `blur(30px) saturate(140%)` at line 276. The trigger
  has not fired: the transparent window is still `never attempted` in
  [docs/host/tasks/014-os-window-polish.md](../../host/tasks/014-os-window-polish.md), so the v1
  ground behind the panel is opaque and nothing is visibly lost yet. One inconsistency was fixed
  while reading. The stylesheet comment named only that host task, which covers the window and says
  nothing about the blur trade, while the origin decision and
  [overlay-ux.md](../../design/overlay-ux.md) both point at this backlog; the comment now names this
  file for the trade and the host task for the pass, matching how the reserved-rail comment 160
  lines above it cites its own task file.
