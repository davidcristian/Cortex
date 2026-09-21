# A Thoughts trace pushing the reply out of view

**Status:** done 2026-08-03
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

Opening a Thoughts trace grew the history from the top while `scrollTop` stayed where it was, so
everything below the trace slid down. Measured 2026-07-20 at 640x720: the reader's distance from
the end of the reply grew from 0 to 76px, and a trace long enough to reach its own `28vh` limit
pushed the answer off screen entirely.

Fixed in `overlay/logRoll.ts`, which keeps the reader's distance from the end of the log constant
for every frame of the opening animation, so the growth comes out of the scroll position instead
of out of the reply. There is no second animation: the scroll position is recomputed from the box
on each frame, so it follows the height animation's timing, and `Collapse.tsx` is unchanged. A
reader who has scrolled up is left alone, and the scroll stops once the opening section's top edge
reaches the top of the window. Traced at 60Hz at 640x720 afterwards: the distance from the end
reads 3px on every frame in both directions, `scrollTop` goes 408 to 484 and back, the largest
single frame is 12px, and the movement runs from t=44ms to t=311ms.

Closing a trace that sits above the visible area now eases `scrollTop` down with the shrink, which
is what the browser's own scroll anchoring did before `.history` turned it off
([ADR-0035](../../adr/ADR-0035-console-and-motion.md) decision 15). Under `prefers-reduced-motion`
there is no animation and the log stays still.

## History

- 2026-07-20: Opened when the disclosure learned to animate open.
- 2026-08-03: Closed. Two details in the original entry were wrong: the measured setup no longer
  exists (the reminder stack only shows on an empty log, and the panel's maximum height at that
  window size is 450px, not 547px), and no second animation was needed, because recomputing the
  scroll position from the box each frame inherits the timing of the height animation.
