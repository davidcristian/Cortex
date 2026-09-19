# A section's roll ends 0.25px short

**Status:** done 2026-08-06
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md), the chat's floor under the empty state ([overlay-ux.md §3](../../design/overlay-ux.md))

`Collapse` measured the height it rolls to with `offsetHeight`
(`body/app/src/components/Collapse.tsx`), which is a whole number, and an opening roll
deliberately does not fill, so the section hands itself back to its own layout when the animation
ends and steps by the difference. The panel's arrival placement (`panelRide.ts`) then added that
rounded target to two fractional heights, so its prediction of where the roll leaves the panel was
out by the same amount. Opened 2026-08-06 by [R-150](150-retarget-from-rounded-height.md), which
took the panel's own measurement off `offsetHeight` and left this one on it.

**Shipped 2026-08-06, hours after it was filed, and both published numbers reproduced exactly**
([ADR-0035](../../adr/ADR-0035-console-and-motion.md)). Re-instrumented at HEAD in headless
Chromium at 900x1000 over the demo, `Element.prototype.animate` hooked before the app loaded and
every painted frame sampled: the aside stands at 193.75px with an `offsetHeight` of 194, and a
section at 57.25 against 57 is there too. That second one is a reminder row and not a Thoughts
trace, which measures 76 flat at this viewport, so the entry named the right number on the wrong
element. The summon's own roll of the aside opened `0px` to `194px` and was handed back to its
layout at 193.75; the closing roll then started at 194 with the eye on 193.75, a 0.25px step up in
a single frame that the panel's `auto` height took with it (545.75 to 546). The arrival placement
predicted 546 for a roll that left the panel at 545.75.

After, the roll measures with the used height the panel reads its own box with (`heightOf`), so
both sides of the roll contract hold one number instead of two roundings of it. The aside rolls
`0px` to `193.75px` and publishes `data-morphing="193.75"`, the prediction is the 545.75 the panel
ends at, and the step at every roll boundary in the trace is 0.000px, which is under the 0.015px
the panel's own change reached because there is no longer any arithmetic to round. The reading
passes the same check the panel's did, the used height ignoring the summon's scale transform where
the rect does not.

The harness moved with it, which is what the entry priced. The prototype-wide stand-in
(`stubRoll`) and `Collapse.test.tsx`'s own now say the height through the computed style, so the
three files sharing them assert on what production reads, and `laysEverything` was widened to take
an answer that changes under the test, which is what a roll interrupted mid-flight needs. Proved
able to fail both ways: put `offsetHeight` back and 11 `Collapse` cases fail along with the
per-row exits in `Reminders.test.tsx` and `SessionList.test.tsx`; round the used height instead
and exactly one case fails, the new one that names the sub-pixel.

## History

- 2026-08-06: Opened by the fractional-height change and shipped hours later the same day. It
  opened the whisper bubble's rounded roll target behind it
  ([R-152](152-whisper-rounded-roll-target.md)), so the area held at twelve, one out and one in.
