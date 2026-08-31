# The whisper bubble's rounded roll target

**Status:** landed 2026-08-07
**Area:** body-overlay
**Origin:** [ADR-0037](../../adr/ADR-0037-whisper-streaming.md)

`useWhisperClock` sets the roll contract's attribute to `String(Math.round(tH))` and writes the
box itself with `${s.h.toFixed(1)}px` (`body/app/src/whisper/useWhisperClock.ts`), so the panel's
ride-along adds a whole-pixel prediction to fractional heights for the length of every streamed
reply, which is the same mismatch the section's roll above had. Noticed 2026-08-06 while taking
that one off `offsetHeight`, and read from the code rather than measured: the bubble is not
handed back to layout at the end of its roll the way a section is, so the visible symptom (a step
when the animation is taken away) may not exist here at all, and the prediction error is bounded
by half a pixel against a 2px floor for animating anything. Deferred as unmeasured: the honest
first move is a live trace of a streamed reply at 900x1000 against the panel's settled height,
and only then a change. The trigger is any panel step seen at the end of a reply, or the next
visit to the whisper's clock.
- **MEASURED FIRST and then LANDED 2026-08-07, and the trace changed what the entry is about**
  ([ADR-0035 addendum](../../adr/ADR-0035-console-and-motion.md),
  [ADR-0037 addendum](../../adr/ADR-0037-whisper-streaming.md)). Headless Chromium at 900x1000 over
  the demo, `Element.prototype.animate` hooked before the app loaded and every painted frame
  sampled once the frame's rendering steps were done, the panel's used height read off the
  computed style so the summon's scale transform is out of it. One reply wrapped five times. The
  bubble published `45`, `67`, `90`, `112` and `135` while the heights it was easing to were
  45.475, 67.475, 90.475, 112.475 and 135.475, a whole `offsetTop` plus a 22.475px line box plus
  10px of padding landing on a x.475 every time. Its box is written to a tenth of a pixel, so the
  height the bubble stands on at the end of each line is 45.5 through 135.5 and every published
  target was exactly half a pixel under it, not the fraction of one the entry allowed for. At the
  last frame of the roll the ride-along's arithmetic read 390.469 for a panel that settled at
  390.969.
- **The step the entry doubted is not there, and it is not there for a stronger reason than the
  entry gave.** Across 172 frames inside the roll there is no frame in which the panel's height
  moves and the bubble's does not; the panel's largest single-frame move is 3.907px, which is the
  bubble's own 3.906px of eased growth arriving one for one. The reason is not only that the
  bubble is never handed back to layout. It is that the prediction never reaches the panel's
  height at all: `rideAlong` finds nothing of the panel's own in the air and the bottom edge
  already where it wants it, so it returns at its common-case branch, and `Element.prototype.animate`
  is called zero times on the panel across the whole reply. The number was computed five times,
  once per wrap, and discarded five times.
- **Two of the entry's own sentences were wrong, and one omission mattered.** The prediction is
  not added "for the length of every streamed reply": the target only changes at a wrap and the
  placement only re-predicts when the published number changes, so it is five predictions in a
  reply of about three seconds and not one per token. And the error is not merely bounded by half
  a pixel, it is half a pixel, every line, by construction. What the entry missed is that the
  prediction is not only a prediction. On an arrival `rideAlong` also pins the panel's bottom edge
  to the centre of the predicted height, and that edge is kept for the session. Traced by
  dismissing to the orb mid-reply and summoning back inside the roll: the panel pinned itself to
  316.59375px where the height the roll actually leaves it at centres on 316.34375px, and it stood
  on the wrong quarter pixel for the rest of the session. Planting `+ 20` on the published target
  moved that edge to 306.59375px, a move of exactly half the plant, which is the gain the
  arithmetic predicts and the proof the published number reaches the edge.
- **The instrument was falsified before it was trusted.** Putting `offsetHeight` back into
  `Collapse` reproduced the sibling's pre-fix reading exactly through this same trace: the
  reminder aside stands at 193.75px, its closing roll opened at 194 with the eye on 193.75, and
  the panel's `auto` height took the 0.25px step along in one frame, 545.75 to 546. A trace that
  can see that can see anything this entry was worried about.
- **After: the roll publishes the number its own box carries** (`tH.toFixed(1)`, the rounding the
  box is written with), so both sides of the contract hold one number instead of two roundings of
  it. Same instrument, same window: the bubble publishes `45.5`, `67.5`, `90.5`, `112.5` and
  `135.5`, the arithmetic at the last frame of the roll reads 390.969 against a settled 390.969,
  and the summon inside the roll pins 316.34375px. The residual is 0.000px here rather than the
  0.015px grid the panel's own change left, because the final target lands on Chromium's 1/64
  grid; a target that does not can still differ from the box by up to 1/64px, which is that same
  known floor and not a new deferral. `useWhisperClock.test.ts` holds the contract as one case
  that lays a wrapped line on a 22.475px line box and asserts the published target against the
  height the box settles at. Falsified three ways: rounding to a whole pixel, publishing the
  unrounded target, and publishing it to two decimals each make that case fail and nothing else.

## Trail

- 2026-08-06: Noticed in the doing of the section-roll entry, which came off `offsetHeight` that
  day, and filed unmeasured because the honest first move here is a live trace rather than a change.
  The area held over that pair, one entry out and one in.
- 2026-08-07: Closed after the trace it asked for, one out and none in, with every top-level entry
  in the area walked beforehand and the index cell agreeing with them name for name. The ledger
  reads it as an entry that was right about the symptom and wrong about the arithmetic on both sides
  of it, and whose change was justified by the thing it had not imagined, the published number
  doubling as the panel's pinned edge on a summon that lands inside the roll. The instrument was
  falsified before it was trusted, and nothing was deferred behind it.
