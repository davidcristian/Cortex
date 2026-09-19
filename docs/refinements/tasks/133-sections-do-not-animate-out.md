# Sections do not animate out

**Status:** done 2026-07-19
**Area:** body-overlay
**Origin:** [ADR-0033](../../adr/ADR-0033-panel-growth.md)

The panel's size change eases in both directions, but a removed section vanished on the first
frame, because React unmounts a removed child immediately. Animating an exit means keeping the
element mounted through it, which is what shipped as `components/Collapse.tsx`: it holds its
children through the close and animates its own height. One component, no reducer change
([ADR-0034](../../adr/ADR-0034-panel-views.md) decision 4).

The cost estimate was right and the description of the symptom was wrong. The mismatch was not
"barely visible": the section's rows vanished, everything below them snapped up into the hole, and
the panel eased down afterwards, which the user reported as the animation feeling wrong. Two
lessons. A defect described as cosmetic deserves one look at the actual frames before it is sized,
and "the collapse the eye follows is the panel's" was an assumption made without watching it.

## History

- 2026-07-19: Filed with the panel's size and shipped the same day, after the user reported the
  animation feeling wrong.
