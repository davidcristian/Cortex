# A placement computed for a stale height

**Status:** landed 2026-08-03
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

`usePanelMotion` runs
on renders and on `cortex:morphend`, so content that resizes the panel without either (the demo's
canned chat settles 1.9px after its last render) leaves the last placement standing. It is
half-priced now that the resting panel is centred rather than derived from the ceiling, a stale
height costing half its error rather than all of it: measured 2026-07-20 at a 900px viewport, the
panel rests at `bottom: 177px` where its real 545.75px earns 177.1px, and every switcher round
trip after it is bit-exact. The fix is a `ResizeObserver` on the panel driving the same placement
the morph end event does, which would also retire the event; the care needed is that the observer
must not conflict with the animations, since every placement resizes the element it is watching.
- **LANDED 2026-08-03 as the observer this entry names, `overlay/panelWatch.ts`, and the event
  STAYS** ([ADR-0035 addendum](../../adr/ADR-0035-console-and-motion.md)). It cannot be retired,
  which the observer is itself the instrument for saying: a roll ends without changing the panel's
  size at all, an opening roll filling nothing so its last value is the height the element already
  has and a closing one filling forwards at zero. Instrumented at 900x900 across the reminder
  stack's roll, the last notification lands at t=456 with the panel at 518 and `cortex:morphend`
  fires at t=471 with none anywhere near it, the next arriving 2.3 seconds later when a
  conversation is loaded. The published cost did not move and could not have: it was at most a
  pixel by this entry's own measurement, and the demo's canned chat no longer settles after its
  last render at all, so that 1.9px could not be reproduced at HEAD. What changed is that the
  panel is now placed for the height it has. The general case, measured rather than argued: 40px
  of content appended straight into the log from the console, where React never hears about it,
  moved the panel's top edge 368.13 to 328.13 in one frame before, and now runs 368.13, 365.77,
  355.66, 342.16, 334.52, 330.59, 328.67, 328.02, 328.13 over about 120ms. The care this entry
  names is the whole of the design and is written out in the addendum: a roll owns the height, a
  move of the panel's own owns it too, a reading with nothing behind it is answered with nothing,
  and the watch is lifted for the frame the panel writes in, because an observer that resizes its
  own target inside its own callback is the one case the specification's depth rule cannot
  deliver and reports as a loop error (measured over the demo: one error event per keystroke that
  grew the pill, now zero).

## Trail

- 2026-07-20: Measured at a 900px viewport and filed as half-priced, the resting panel being centred
  rather than derived from the ceiling.
- 2026-08-03: Landed as `overlay/panelWatch.ts`, the observer it names, and closed as one pickup
  with the composer's own growth, the two being the same fix. The `cortex:morphend` event is not
  retired and cannot be, which the observer is itself the instrument for saying: a roll ends without
  changing the panel's size at all, so nothing else says a roll is over.
