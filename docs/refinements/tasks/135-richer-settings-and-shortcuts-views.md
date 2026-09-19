# Two richer directions for the settings and shortcuts views

**Status:** done 2026-07-20
**Area:** body-overlay
**Origin:** [ADR-0034](../../adr/ADR-0034-panel-views.md)

Three designs were pitched to the user and the plainest shipped first: rows, hairlines, one way
back. The maintainer then picked the other two together, and both were built as predicted, as
inner markup on plumbing that did not move. The theme choices are thumbnails of the panel in each
theme, and the two destinations became one console with a tab strip
([ADR-0035](../../adr/ADR-0035-console-and-motion.md) decision 1). The motion is the panel's
existing view morph, because the tab is part of the view name, so the geometry did not change.

## History

- 2026-07-19: Opened with the panel's views, two richer directions pitched and not picked.
- 2026-07-20: The user picked both at once and both shipped as predicted.
