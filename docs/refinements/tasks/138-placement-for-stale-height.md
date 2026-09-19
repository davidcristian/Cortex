# A placement computed for a stale height

**Status:** done 2026-08-03
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

`usePanelMotion` ran on renders and on `cortex:morphend`, so content that resized the panel
without either left the last placement in place. The entry priced it at half its error, since the
resting panel is centred rather than derived from the ceiling: measured 2026-07-20 at a 900px
viewport, the panel rests at `bottom: 177px` where its real 545.75px gives 177.1px, and every
switcher round trip after it is exact. The fix it named is a `ResizeObserver` on the panel driving
the same placement the morph-end event does.

**Shipped 2026-08-03 as `overlay/panelWatch.ts`, and the event stays**
([ADR-0035](../../adr/ADR-0035-console-and-motion.md)). The observer is itself the instrument for
saying why it cannot be retired: a roll ends without changing the panel's size at all, an opening
roll filling nothing so its last value is the height the element already has, and a closing one
filling forwards at zero. Instrumented at 900x900 across the reminder stack's roll, the last
notification arrives at t=456 with the panel at 518 and `cortex:morphend` fires at t=471 with no
notification anywhere near it, the next arriving 2.3 seconds later when a conversation is loaded.

The published cost did not move and could not have: it was at most a pixel by this entry's own
measurement, and the demo's canned chat no longer settles after its last render, so the 1.9px
could not be reproduced at HEAD. What changed is that the panel is now placed for the height it
has. Measured on the general case: 40px of content appended straight into the log from the
console, where React never hears about it, moved the panel's top edge 368.13 to 328.13 in one
frame before, and now runs 368.13, 365.77, 355.66, 342.16, 334.52, 330.59, 328.67, 328.02, 328.13
over about 120 ms.

The care the entry named is the whole of the design, written out in ADR-0035 decision 32: a roll
controls the height, a move of the panel's own controls it too, a reading with nothing behind it
changes nothing, and the watch is lifted for the frame the panel writes in, because an
observer that resizes its own target inside its own callback is the one case the specification's
depth rule cannot handle and reports as a loop error (measured over the demo: one error event per
keystroke that grew the pill, now zero).

## History

- 2026-07-20: Measured at a 900px viewport and filed as half-priced.
- 2026-08-03: Shipped as `overlay/panelWatch.ts`, and closed as one pickup with the composer's own
  growth ([R-139](139-composer-growth-never-eased.md)), the two being the same fix.
