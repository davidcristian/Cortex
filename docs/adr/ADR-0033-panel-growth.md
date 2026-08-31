# ADR-0033: The panel grows upward, and its size changes are animated

- **Status:** Accepted, amended by [ADR-0034](ADR-0034-panel-views.md)
- **Date:** 2026-07-19

> **What changed.** Decision 1's fixed `bottom: 15vh` is gone: the panel re-centres on a view change
> and pins its bottom edge only *within* a view, which keeps the composer still without leaving a
> short panel permanently below centre. Decision 5's `sectionin` is gone too, replaced by sections
> that animate their own height (ADR-0034 decision 4), which is also the answer to consequence 3's
> unanimated exits. Decisions 2, 3, 4 and 6 stand and are why the rest works.

## Context

The overlay panel was anchored by its middle (`top: 46%` with a `translate(-50%, -50%)`), so every
size change split the difference between its top and bottom edges. Opening the chat switcher,
pulling in reminders, or streaming a long reply moved the composer down as the panel grew, out
from under the hand that had just typed into it. Size changes were also instant: the panel jumped
from one height to the next.

## Decision

1. **The panel is anchored by its bottom edge** (`bottom: 15vh`, `transform-origin: 50% 100%`).
   Everything that resizes it therefore grows it upward and the composer stays exactly where it
   was. `15vh` is chosen so a full-height panel occupies nearly the band it always did (its top
   edge lands within a percent of the old layout); what moves is where a *short* panel sits, which
   is now bottom-aligned with the tall one rather than floating in the middle.

2. **Size changes are animated in code, not CSS.** `overlay/useGrowthAnimation.ts` measures the
   element in a layout effect and replays the change through the Web Animations API. This is the
   part worth writing down, because the CSS-only version looks right and does nothing: a
   `transition: height` never fires when the height is `auto` on both sides and only the content
   changed, since no computed value changed. `interpolate-size: allow-keywords` does not rescue
   it either; it makes `auto` interpolable against a **length** (`height: 0` to `height: auto`,
   the accordion case), not one content-driven `auto` against the next. Both were written, shipped
   into a browser, and measured: opening the switcher moved the panel through exactly **one**
   distinct height.

3. **The running animation is cancelled before each measurement.** A height animation overrides
   the element's used height, so measuring mid-ease returns the in-flight value rather than the
   natural one. Reading it anyway produces a specific and ugly failure: during a stream every
   token animates from in-flight to in-flight, the panel never converges on its content height,
   and the reply sits permanently clipped by `overflow: hidden`. The order is therefore: read what
   is displayed, cancel, read the natural height, animate between the two. That also makes a
   change mid-ease continuous, since the new animation starts where the old one was. This was a
   real defect in the first implementation, caught in the browser, and it has its own test.

4. **`overflow: hidden` on the panel makes the animation a reveal.** Mid-ease the panel is shorter
   than its content, so new rows are clipped by the rounded edge instead of spilling past it.

5. **Sections rise as the space appears.** The switcher list and the reminder stack fade and
   translate in (`sectionin`) while the panel grows to fit them, so the two motions read as one
   rather than a list appearing inside a box that is still moving.

6. **Reduced motion schedules nothing**, and neither does a closed or minimized panel: the
   open/close pop and the corner travel to the orb are transforms that own their own motion.
   Heights are still *measured* while closed, so a reopen at a new size animates from a real
   height rather than a stale one.

## Consequences

- The panel is lower on screen when short (an empty chat now sits bottom-aligned rather than
  centered). That is the deliberate trade for a composer that never moves.
- `Panel` re-renders per streamed token already, and each render now costs one `getBoundingClient
  Rect` and possibly one animation replacement. Height animations are not compositor-friendly (they
  drive layout), so this is the one place in the overlay that animates a layout-affecting property
  on purpose; it is bounded by the panel being a single element with a handful of children.
- Exit animations are not covered: React unmounts a removed section immediately, so a closing
  switcher collapses through the panel's height ease but the list itself vanishes rather than
  sliding out. Recorded in `docs/refinements/index.md#body-overlay` rather than solved here, because
  animating unmount means keeping the element mounted through its exit.

## Addendum (2026-07-21): an arriving aside is counted off the raw height

The maintainer caught a two-beat summon: with the day's reminders rolling in behind the pop, the
part under the stack squeezed a little further after the main movement finished, and a small
second ease then gave it back. Nothing of the kind happens entering or leaving the console,
which is what made it stand out.

The defect was in the ride-along's arrival centring. It subtracted the aside's height from a
panel-height prediction the OLD edge's ceiling had already clamped, so the chat was centred on
what was left of a number the ceiling had already cut down rather than on its own height. That
pinned an edge the whole panel could not fit above, the cap written for that edge squeezed the chat
under the rolling stack, and the first placement after the roll recomputed from the raw height and
undid it. Traced at a 760px viewport with the demo's reminders: the history lost 119px over the roll
and a 40px ease handed most of it back a beat after the pop settled.

The aside is now counted off the RAW prediction (bounded by `openHeight`, the same loose cap an
ordinary placement measures under), and the height the roll is placed for is capped by the
ceiling of the edge that centring actually picks. The two deciders agree on the edge, so the
placement after the roll finds nothing left to move: re-traced, the bottom edge stands still
from summon to settle, the panel grows to its honest ceiling during the roll, and the history
shrinks once, to the height it keeps.

A second look found the part the edge fix alone did not address: with the edge standing
still the second ease was gone, but the squeeze itself had only moved inside the roll. The
panel's `auto` height followed the roll one-for-one until the cap applied, and the stack's
remaining growth then compressed the chat in the roll's tail, so the empty state held its size
and resized only at the end. An arrival whose section outgrows the ceiling now CARRIES the
panel's height, the mechanism interrupted eases already use, driving it to the predicted
height over the roll's own clock and curve, so the chat's window compresses in step with the
stack growing. Re-traced at the same 760px: the history eases monotonically from 195 to its
final 116 across the whole roll, one animation, no phase change, and the placement after the
roll still finds nothing to move.
