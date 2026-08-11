# A mid-stream retarget restarts from a rounded height

**Status:** landed 2026-08-06
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md), the chat's floor under the empty state ([overlay-ux.md §3](../../design/overlay-ux.md))

The panel measures itself with
`offsetHeight` (`overlay/panelMemory.ts`), which is a whole number, and during a stream every
token retargets the move: `place` cancels what is running, reads where the panel is, and opens
the new animation's keyframes there. So the new move starts on the rounded pixel while the eye
has the fractional one, and the panel steps back by the remainder for a frame. Measured 2026-07-20
at 60Hz with `element.animate` instrumented, at 640x720 with the reminder stack acked, over one
streamed reply: every down-step of the exchange lands on a frame carrying such a call, opening on
exactly the rounded value (363.188 to 363 against `363px`, 365.344 to 365 against `365px`,
386.328 to 386 against `386px`). Worst step anywhere is 0.39px; there are none at all at 640x720
with the stack up, the panel being pinned at its ceiling. This is bounded and it is not the
user's complaint: across five traced configurations the panel is never below its pre-send height
at any frame, so the floor holds and what is left is invisible. The fix is to read the used height
with its sub-pixels (`parseFloat(getComputedStyle(element).height)`, which Chromium resolves to
the border-box height under this app's `box-sizing: border-box`, measured here as 363.188px
against an `offsetHeight` of 363 on a panel with a 1px border). It is deferred because
`offsetHeight` is what the hook and its fakes are built on: every case in
`overlay/usePanelMotion.test.ts` defines `offsetHeight` on the element, so the swap is a harness
rewrite for a snap no eye can see, and it would want the same check `offsetHeight` was given
against the summon's scale transform before `Collapse` follows it, or the two measure differently.
- **Not to be confused with the second rounding, which was a defect and is fixed.** A re-read
  measured a whole pixel at 640x720 with the stack up, which is exactly where this entry says
  there is nothing, and the two are unrelated: that one was `maxHeight` rounded on the way out to
  `max-height` and taken raw as the cap on a roll's predicted height, so a panel at its ceiling
  was placed for a height 0.2px taller than it could have and its bottom edge rounded the other
  way
  ([ADR-0035](../../adr/ADR-0035-console-and-motion.md) decision 16). This entry remains what it says: a
  fractional used height against a rounded `offsetHeight`, while a stream retargets a move.
- **LANDED 2026-08-06 with the entry above, and the harness rewrite was the whole of the cost it
  said it was** ([ADR-0035 addendum](../../adr/ADR-0035-console-and-motion.md)). Re-instrumented at
  HEAD at 900x1000 with the stack acked, over one streamed reply: 310 of 330 readings of the
  panel's `offsetHeight` threw a sub-pixel away, worst 0.484px, all three of the panel's moves
  opened on a whole number, and the painted top edge stepped back 0.281px at the frame a retarget
  opened at 459 against a panel standing at 459.281. At 640x720 with the stack up there is still
  nothing at all, the panel making no moves of its own. After: the panel's `offsetHeight` is read
  zero times, none of the four openings is whole, and the worst step is 0.015px, which is
  Chromium's own 1/64px grid rather than anything left to fix.
  **The reading passes the check this entry asked for.** Measured on a 356.281px box with a 1px
  border: `offsetHeight` reads 356 whether or not the box is scaled, the rect reads 356.266 plain
  and 327.764 under `scale(0.92)`, and the used height reads 356.266 under both. Live at 900x900,
  120ms into a summon, the panel's rect reads 511.626 against a used height of 518, and the
  session is pinned to the same 274px edge on every summon.
  **A second rounding of the same shape was found beside it and fixed in the same change.** The
  bottom edge was written rounded while the keyframe went to the fraction, so at 901x1001 a whole
  ease painted a 324.5px edge and the frame that removed the animation handed back 325. Half a
  pixel, which is larger than the artefact this entry is about, on the same element in the same
  keyframes.
  **The harness rewrite is what the entry priced, and it landed as one helper rather than as a
  rewrite per file.** Every fake of `offsetHeight` for a box the panel measures now says the same
  thing through the computed style (`lays`, `laysEverything` in `body/app/src/test-setup.ts`),
  which is four call sites across `usePanelMotion.test.ts`, `measured.test.ts`, `Panel.test.tsx`
  and `Message.test.tsx`. The fake models the probe the way the cascade does, answering the panel's
  own layout while an important inline height is standing, so no test asserts on a number
  production does not read. What the entry named as wanting the same check, `Collapse` following,
  is the one part not done and is the entry below.

## Trail

- 2026-07-20: Measured at 60Hz with `element.animate` instrumented, worst step 0.39px, and deferred
  on the harness cost, `offsetHeight` being what the hook and its fakes are built on.
- 2026-08-03: Read on both sides of two changes that landed in this area that day and unmoved by
  either. The panel-watch sitting recorded this entry putting the panel through 2 to 3 animations
  per reply either way, and the chat-floor sitting recorded no sub-pixel step anywhere in a streamed
  reply either way.
- 2026-08-06: Landed with the resize-inside-a-move entry, and the harness rewrite was the whole of
  the cost it said it was, landing as one helper rather than as a rewrite per file. Before, 310 of
  330 readings threw a sub-pixel away and the painted top edge stepped back 0.281px; after, the
  worst step is 0.015px, which is Chromium's own grid. A second rounding of the same shape, the
  bottom edge written rounded against a fractional keyframe, was found beside it and fixed in the
  same change. The pair opened the section roll behind them, being the same reading one element
  down.
