# A section's roll ends 0.25px short

**Status:** landed 2026-08-06
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md), the chat's floor under the empty state ([overlay-ux.md §3](../../design/overlay-ux.md))

`Collapse` measures the height it is
rolling to with `offsetHeight` (`body/app/src/components/Collapse.tsx`), which is a whole number,
and an opening roll deliberately does not fill, so the section hands itself back to its own layout
when the animation ends and steps by the difference. Measured 2026-08-06 at 900x1000 over the
demo: the reminder stack's aside is 193.75px against a 194px target, and a Thoughts trace is
57.25px against 57. The panel's ride-along then adds that rounded target to two fractional heights
(`panelRide.ts`), so its prediction of where the roll leaves the panel is out by the same amount,
which is far under the 2px below which nothing is animated at all. Opened 2026-08-06 by the
fractional-height change above, which took the panel's own measurement off `offsetHeight` and left
this one on it. It is deferred because the reading is one line and the harness around it is not:
the roll stand-in that every per-row exit is asserted through fakes `offsetHeight` on the
prototype and is shared by three test files, so following the panel means moving all of them. The
trigger is a roll whose end is visible at all: a section whose natural height lands nearer the
half pixel, or any report of a section settling with a flick.
- **LANDED 2026-08-06, hours after it was filed, and both published numbers reproduced exactly**
  ([ADR-0035 addendum](../../adr/ADR-0035-console-and-motion.md)). Re-instrumented at HEAD in
  headless Chromium at 900x1000 over the demo, `Element.prototype.animate` hooked before the app
  loaded and every painted frame sampled: the aside stands at 193.75px with an `offsetHeight` of
  194, and a section at 57.25 against 57 is there too. That second one is a reminder ROW and not a
  Thoughts trace, which measures 76 flat at this viewport, so the entry named the right number on
  the wrong element. The summon's own roll of the aside opened `0px` to `194px` and was handed
  back to its layout at 193.75; the closing roll then started at 194 with the eye on 193.75, a
  0.25px step up in a single frame that the panel's `auto` height took with it (545.75 to 546).
  The ride-along predicted 546 for a roll that left the panel at 545.75, which is the same 0.25px
  inherited exactly as the entry said.
- **After: the roll measures with the used height the panel reads its own box with** (`heightOf`),
  so the two sides of the roll contract hold one number instead of two roundings of it. The aside
  rolls `0px` to `193.75px` and publishes `data-morphing="193.75"`, the ride-along's prediction is
  the 545.75 the panel lands on, and the step at every roll boundary in the trace is 0.000px:
  under the 0.015px the panel's own change reached, because there is no longer any arithmetic to
  round rather than because the grid got finer. The reading passes the check the entry asked for
  and it is the same check the panel's did, the used height ignoring the summon's scale transform
  where the rect does not.
- **The harness moved with it, which is what the entry priced.** The prototype-wide stand-in
  (`stubRoll`) and `Collapse.test.tsx`'s own now say the height through the computed style, so the
  three files sharing them assert on what production reads; `laysEverything` was widened to take
  an answer that changes under the test, which is what a roll interrupted mid-flight needs.
  Falsified both ways: put `offsetHeight` back and 11 `Collapse` cases redden along with the
  per-row exits in `Reminders.test.tsx` and `SessionList.test.tsx`; round the used height instead
  and exactly one case reddens, the new one that names the sub-pixel.

## Trail

- 2026-08-06: Opened by the fractional-height change above, which took the panel's own measurement
  off `offsetHeight` and left this one on it, and landed hours later the same day with both
  published numbers reproducing exactly at HEAD. The 57.25px section is a reminder row rather than
  the Thoughts trace the entry named, which measures 76 flat at that viewport. The step at every
  roll boundary reads 0.000px after, the harness moved with it, and reverting the reading reddens
  eleven `Collapse` cases. It opened the whisper bubble's rounded roll target behind it, so the area
  held at twelve, one out and one in.
