# Sections do not animate out

**Status:** landed 2026-07-19
**Area:** body-overlay
**Origin:** [ADR-0033](../../adr/ADR-0033-panel-growth.md)

This is [ADR-0034](../../adr/ADR-0034-panel-views.md) decision 4.
The deferral read: the panel's size
change eases in both directions, but the section itself vanishes on the first frame because
React unmounts a removed child immediately, and animating an exit means keeping the element
mounted through it. That is exactly what shipped, and the guess about the cost was right and
the guess about the symptom was wrong. It cost one component (`components/Collapse.tsx`, which
holds its children through the close and animates its own height) and no reducer change at all.
But the asymmetry was not "barely visible": the section's rows vanished, everything below them
snapped up into the hole, and the panel eased down afterwards, which the user reported as the
animation feeling wrong. Two lessons for the next entry of this shape. A defect described as
cosmetic deserves one look at the actual frames before it is sized, and "the collapse the eye
follows is the panel's" was an assumption about what the eye follows, made without watching it.

## Trail

- 2026-07-19: Filed with the panel's size and landed the same day as `components/Collapse.tsx`, one
  component and no reducer change, after the user reported the animation feeling wrong.
