# Two richer directions for the settings and shortcuts views

**Status:** landed 2026-07-20
**Area:** body-overlay
**Origin:** [ADR-0034](../../adr/ADR-0034-panel-views.md)

What shipped first was the plainest of three pitched to the user: rows, hairlines,
one way back. The maintainer picked the other two together, and both were built as predicted, inner
markup on plumbing that did not move: the theme choices are thumbnails of the panel in each
theme, and the two destinations are one console with a tab strip
([ADR-0035](../../adr/ADR-0035-console-and-motion.md) decision 1). The motion is the panel's
existing view morph, because the tab is part of the view name, so nothing about the geometry
changed.

## Trail

- 2026-07-19: Opened with the panel's views, two richer directions pitched and unpicked.
- 2026-07-20: The user picked both at once and both landed as predicted, a component change on
  plumbing that did not move.
