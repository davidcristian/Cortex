# ADR-0033: The panel grows upward, and its size changes are animated

**Status:** Accepted (2026-07-21), amended by [ADR-0034](ADR-0034-panel-views.md)

## Context

The overlay panel was anchored by its middle (`top: 46%` with a `translate(-50%, -50%)`), so every
size change split the difference between its top and bottom edges. Opening the chat switcher,
fetching reminders, or streaming a long reply moved the composer down as the panel grew, out from
under the hand that had just typed into it. Size changes were also instant: the panel jumped from
one height to the next.

This ADR covers how the panel's height changes. Where its bottom edge is placed (centred on a
summon, kept across a view change, restored on returning to the chat) is
[ADR-0034](ADR-0034-panel-views.md) and [ADR-0035](ADR-0035-console-and-motion.md).

## Decision

1. **Within a view, the panel grows from its bottom edge** (`transform-origin: 50% 100%`, the
   edge fixed where the panel was placed). Everything that resizes it therefore grows it upward
   and the composer stays exactly where it was. The first version fixed that edge at
   `bottom: 15vh` for the whole session, which left a short panel permanently below centre;
   [ADR-0034](ADR-0034-panel-views.md) decision 2 replaced the fixed edge with one placed on each
   summon and held still only within a view.

2. **Size changes are animated in code, not CSS.** `overlay/panelPlacement.ts` measures the
   element in a layout effect (`overlay/usePanelMotion.ts`) and replays the change through the Web
   Animations API. This is the part worth writing down, because the CSS-only version looks right
   and does nothing: a `transition: height` never runs when the height is `auto` on both sides
   and only the content changed, since no computed value changed. `interpolate-size:
   allow-keywords` does not rescue it either; it makes `auto` interpolable against a **length**
   (`height: 0` to `height: auto`, the accordion case), not one content-driven `auto` against the
   next. Both were written, shipped into a browser, and measured: opening the switcher moved the
   panel through exactly **one** distinct height.

3. **The running animation is cancelled before each measurement.** A height animation overrides
   the element's used height, so measuring mid-ease returns the in-flight value rather than the
   natural one. Reading it anyway produces a specific and ugly failure: during a stream every
   token animates from in-flight to in-flight, the panel never reaches its content height, and the
   reply sits permanently clipped by `overflow: hidden`. The order is therefore: read what is
   displayed, cancel, read the natural height, animate between the two. That also makes a change
   mid-ease continuous, since the new animation starts where the old one was. This was a real
   defect in the first implementation, caught in the browser, and it has its own test.

4. **`overflow: hidden` on the panel makes the animation a reveal.** Mid-ease the panel is shorter
   than its content, so new rows are clipped by the rounded edge instead of spilling past it.

5. **Sections animate their own height, and the panel follows them.** A section rolls its own
   height open and shut ([ADR-0034](ADR-0034-panel-views.md) decision 4), and the panel predicts
   the height the roll will leave it at and slides over the same duration and curve
   ([ADR-0035](ADR-0035-console-and-motion.md) decision 5). This replaced the first version's
   `sectionin`, a fade and translate that ran while the panel grew and left a closing section to
   vanish in one frame.

6. **Reduced motion schedules nothing**, and neither does a closed or minimized panel: the
   open/close pop and the corner travel to the orb are transforms with their own motion. Heights
   are still *measured* while closed, so a reopen at a new size animates from a real height rather
   than a stale one.

7. **A section arriving with a summon is subtracted from the panel's raw height.** When a section
   (the day's reminders) rolls in behind the summon, the height the panel is centred for is its
   natural height less the section's height plus the section's target height, bounded only by
   `openHeight`, the loose cap an ordinary placement measures under, and the height the roll is
   placed for is capped by the ceiling of the edge that centring picks (`overlay/panelRide.ts`).
   Subtracting the section from a prediction the old edge's ceiling had already clamped centred
   the chat on a number the ceiling had cut down: it fixed an edge the whole panel could not fit
   above, squeezed the chat under the rolling stack, and a second ease gave the height back a beat
   after the summon settled. With both calculations agreeing on the edge, the placement after the
   roll finds nothing left to move. When the arriving section outgrows the ceiling, the panel
   animates its own height to the predicted one over the roll's timing and curve, the same
   mechanism an interrupted ease uses, so the chat's window compresses together with the section
   growing rather than at the end of the roll.

## Consequences

- `Panel` re-renders per streamed token already, and each render now costs one height read and
  possibly one animation replacement. Height animations are not compositor-friendly (they drive
  layout), so this is the one place in the overlay that animates a layout-affecting property on
  purpose; it is bounded by the panel being a single element with a handful of children.
- A summon with a section rolling in behind it is one movement: the bottom edge stands still from
  summon to settle and the history shrinks once, to the height it keeps
  (`usePanelMotion.test.ts`, "counts an arriving aside off the raw height").

## Alternatives rejected

- **A CSS `transition: height`, with or without `interpolate-size`**: it does not run between two
  `auto` heights (decision 2).
- **Centring the panel by its middle**: every size change moves the composer.

## Related

- Code: `body/app/src/overlay/panelPlacement.ts`, `panelRide.ts`, `usePanelMotion.ts`.
- Design: [overlay-ux.md](../design/overlay-ux.md).
- ADRs: [ADR-0034](ADR-0034-panel-views.md) (where the edge is placed, sections that roll),
  [ADR-0035](ADR-0035-console-and-motion.md) (the panel's motion rules),
  [ADR-0037](ADR-0037-whisper-streaming.md) (the replayed height under a streaming reply).
