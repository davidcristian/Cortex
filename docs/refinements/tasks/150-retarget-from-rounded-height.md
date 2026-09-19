# A mid-stream retarget restarts from a rounded height

**Status:** done 2026-08-06
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md), the chat's floor under the empty state ([overlay-ux.md §3](../../design/overlay-ux.md))

The panel measured itself with `offsetHeight` (`overlay/panelMemory.ts`), which is a whole number,
and during a stream every token retargets the move: `place` cancels what is running, reads where
the panel is, and opens the new animation's keyframes there. So the new move started on the
rounded pixel while the eye had the fractional one, and the panel stepped back by the remainder
for a frame.

Measured 2026-07-20 at 60Hz with `element.animate` instrumented, at 640x720 with the reminder
stack acked, over one streamed reply: every down-step fell on a frame with such a call, opening
on exactly the rounded value (363.188 to 363 against `363px`, 365.344 to 365 against `365px`,
386.328 to 386 against `386px`). Worst step anywhere 0.39px, and none at all at 640x720 with the
stack up, the panel being held at its ceiling.

This is not the same as the other rounding fixed nearby, which was a defect:
`maxHeight` rounded on the way out to `max-height` and taken raw as the cap on a roll's predicted
height, so a panel at its ceiling was placed for a height 0.2px taller than it could have and its
bottom edge rounded the other way
([ADR-0035](../../adr/ADR-0035-console-and-motion.md) decision 16).

**Shipped 2026-08-06 with [R-140](140-resize-inside-panel-move.md), and the harness rewrite was
the whole of the cost the entry predicted.** Re-instrumented at HEAD at 900x1000 with the stack
acked, over one streamed reply: 310 of 330 readings of the panel's `offsetHeight` threw a
sub-pixel away, worst 0.484px, all three of the panel's moves opened on a whole number, and the
painted top edge stepped back 0.281px at the frame a retarget opened at 459 against a panel
reading 459.281. After: the panel's `offsetHeight` is read zero times, none of the four
openings is whole, and the worst step is 0.015px, which is Chromium's own 1/64px grid.

The fix is to read the used height with its sub-pixels
(`parseFloat(getComputedStyle(element).height)`, which Chromium resolves to the border-box height
under this app's `box-sizing: border-box`). It passes the check the entry asked for. Measured on a
356.281px box with a 1px border: `offsetHeight` reads 356 whether or not the box is scaled, the
rect reads 356.266 plain and 327.764 under `scale(0.92)`, and the used height reads 356.266 under
both. Live at 900x900, 120 ms into a summon, the panel's rect reads 511.626 against a used height
of 518, and the session keeps the same 274px edge on every summon.

A second rounding of the same shape was found beside it and fixed in the same change: the bottom
edge was written rounded while the keyframe went to the fraction, so at 901x1001 a whole ease
painted a 324.5px edge and the frame that removed the animation handed back 325.

The harness moved as one helper rather than a rewrite per file. Every fake of `offsetHeight` for a
box the panel measures now says the same thing through the computed style (`lays`,
`laysEverything` in `body/app/src/test-setup.ts`), which is four call sites across
`usePanelMotion.test.ts`, `measured.test.ts`, `Panel.test.tsx` and `Message.test.tsx`. The fake
models the probe the way the cascade does, answering the panel's own layout while an important
inline height is set, so no test asserts on a number production does not read.

What the entry named as wanting the same check, `Collapse` following, is
[R-151](151-section-roll-ends-short.md).

## History

- 2026-07-20: Measured at 60Hz with `element.animate` instrumented, worst step 0.39px, and
  deferred on the harness cost, `offsetHeight` being what the hook and its fakes were built on.
- 2026-08-03: Read on both sides of two changes in this area that day and unmoved by either. The
  panel-watch measurement recorded 2 to 3 animations per reply either way, and the chat-floor
  measurement recorded no sub-pixel step anywhere in a streamed reply either way.
- 2026-08-06: Shipped with the resize-inside-a-move entry. The pair opened the section roll behind
  them, being the same reading one element down.
