# The whisper bubble's rounded roll target

**Status:** done 2026-08-07
**Area:** body-overlay
**Origin:** [ADR-0037](../../adr/ADR-0037-whisper-streaming.md)

`useWhisperClock` set the roll contract's attribute to `String(Math.round(tH))` while writing the
box itself with `${s.h.toFixed(1)}px` (`body/app/src/whisper/useWhisperClock.ts`), so the panel's
arrival placement added a whole-pixel prediction to fractional heights. That is the same mismatch
[R-151](151-section-roll-ends-short.md) had. It was noticed while fixing that one and filed
unmeasured, because the bubble is not handed back to layout at the end of its roll the way a
section is, so the visible symptom might not exist at all.

**Measured first and then shipped 2026-08-07**
([ADR-0035](../../adr/ADR-0035-console-and-motion.md),
[ADR-0037 decision 10](../../adr/ADR-0037-whisper-streaming.md)). Headless Chromium at 900x1000
over the demo, `Element.prototype.animate` hooked before the app loaded and every painted frame
sampled once the frame's rendering steps were done, the panel's used height read off the computed
style so the summon's scale transform is out of it. One reply wrapped five times.

The bubble published `45`, `67`, `90`, `112` and `135` while the heights it was easing to were
45.475, 67.475, 90.475, 112.475 and 135.475, a whole `offsetTop` plus a 22.475px line box plus
10px of padding falling on a x.475 every time. Its box is written to a tenth of a pixel, so the
height the bubble stands on at the end of each line is 45.5 through 135.5 and every published
target was exactly half a pixel under it. At the last frame of the roll the placement's arithmetic
read 390.469 for a panel that settled at 390.969.

The step the entry doubted is not there, for a stronger reason than the entry gave. Across 172
frames inside the roll there is no frame in which the panel's height moves and the bubble's does
not, and the panel's largest single-frame move is 3.907px, which is the bubble's own 3.906px of
eased growth arriving one for one. The prediction never reaches the panel's height at all:
`slideWithRoll` finds nothing of the panel's own in the air and the bottom edge already where it wants
it, so it returns at its common-case branch, and `Element.prototype.animate` is called zero times
on the panel across the whole reply.

Two of the entry's sentences were wrong and one omission mattered. The prediction is not added for
the length of every streamed reply: the target only changes at a wrap and the placement only
re-predicts when the published number changes, so it is five predictions in a reply of about three
seconds. The error is not merely bounded by half a pixel, it is half a pixel, every line. And the
prediction is not only a prediction: on an arrival `slideWithRoll` also fixes the panel's bottom edge
to the centre of the predicted height, and that edge is kept for the session. Traced by dismissing
to the orb mid-reply and summoning back inside the roll, the panel fixed itself to 316.59375px
where the height the roll actually leaves it at centres on 316.34375px, and it stood on the wrong
quarter pixel for the rest of the session. Planting `+ 20` on the published target moved that edge
to 306.59375px, a move of exactly half the plant, which is the gain the arithmetic predicts.

The instrument was proved able to fail before it was trusted: putting `offsetHeight` back into
`Collapse` reproduced the sibling's pre-fix reading exactly through this same trace, the reminder
aside at 193.75px, its closing roll opening at 194 with the eye on 193.75, and the
panel's `auto` height taking the 0.25px step along in one frame, 545.75 to 546.

After, the roll publishes the number its own box is written with (`tH.toFixed(1)`). Same
instrument, same window: the bubble publishes `45.5`, `67.5`, `90.5`, `112.5` and `135.5`, the
arithmetic at the last frame of the roll reads 390.969 against a settled 390.969, and the summon
inside the roll fixes 316.34375px. The residual is 0.000px here rather than the 0.015px grid the
panel's own change left, because the final target falls on Chromium's 1/64 grid; a target that
does not can still differ from the box by up to 1/64px, which is that same known limit and not a
new deferral. `useWhisperClock.test.ts` holds the contract as one case that lays a wrapped line on
a 22.475px line box and asserts the published target against the height the box settles at. Proved
able to fail three ways: rounding to a whole pixel, publishing the unrounded target, and
publishing it to two decimals each make that case fail and nothing else.

## History

- 2026-08-06: Noticed while fixing the section-roll entry and filed unmeasured, because the first
  move here is a live trace rather than a change. The area held over that pair, one out and one in.
- 2026-08-07: Closed after the trace it asked for, one out and none in, with every entry in the
  area walked beforehand and the index cell agreeing with them name for name. It was right about
  the symptom and wrong about the arithmetic on both sides of it, and its change was justified by
  the thing it had not imagined, the published number doubling as the panel's fixed edge on a
  summon that arrives inside the roll.
