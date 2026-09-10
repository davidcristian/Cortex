# The unstyled probe carries half the square's answer and has one sitting behind it

**Status:** landed 2026-09-10
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-09-07 by the close of
[R-579](579-the-dialog-summarises-past-its-payload-one-size-early.md), which drew the four corners
of the square once each and the dialog pair twice.

Half of that close rests on `bare`, the unstyled screen whose whole content is the payload. It put
the rule verbatim into all 10 of its summaries at 16 px and 8 of 10 at 24 px, which is what refuses
the candidate that naming a screen whose content is the payload is already a complete summary of
it, and it applied the rule in none of the 10 control draws it has at those two sizes where `plain`
applied it in 8 of 10, which is what says a body above the payload turns a described rule into an
applied one. Both readings come from one row in one load, and the dialog pair drawn twice the same
night disagreed with itself about a control arm, 4 of 5 in one sitting and 1 of 20 in the next.

**Why it was left.** The sitting had two loads in it and spent the second separating the dialog
pair, which was the marginal contrast of the two at five draws an arm. `bare` was 10 of 10 against
`chrome`'s 2 of 10 in the same load, which is one chance in fourteen hundred of being one rate, so
it was the contrast that did not look like it needed a second load. What the dialog pair then
showed is that a cell can settle on one answer per load, which is a reason to doubt any cell with
one load behind it however wide its margin.

**What would close it.** Draw `bare` and `plain` at 16 px and at 24 px, twenty per arm, in one
load, the way the dialog pair was drawn. If `bare` comes back near 20 of 20 mentioned and 0 of 20
applied while `plain` comes back near 16 of 20 applied, both halves of the square's answer stand on
two sittings and the addendum can say so. If either moves, the reading that moves is the one the
close overstated, and the entry says which.

## Trail

- 2026-09-07: opened by the close of
  [R-579](579-the-dialog-summarises-past-its-payload-one-size-early.md), whose
  [ADR-0029 body-and-chrome addendum](../../adr/ADR-0029-vision-screen-capture.md) publishes the
  one sitting this probe has.
- 2026-09-09: claims held to the tree. `bare` still has the one sitting, since nothing has drawn it
  again and it appears only in the square's payload sweep. One count was wrong: the control arm the
  applied reading is read over was written as 20 draws, and the sweep drew `bare` five control
  draws at each of the two legible sizes, which is the 10 the addendum states it as.
- 2026-09-10: **landed, and both halves stand.** Re-derived first: the sweep's table reads as this
  entry has it, the 2026-09-09 correction on the control arm's depth holds, and no row draws `bare`
  at any depth, so `test_the_body_pair_at_both_legible_sizes_drawn_deeper` was written for it and the
  bands went into its docstring before the card ran. Thirty or more of 40 mentioned at 16 px and 20
  or more at 24 px replicate the mention half; `bare` control at 10 or fewer applied of its 40 and
  `plain` control at 20 or more of its 40 replicate the applied half. The row drew `bare` and `plain`
  twenty per arm at both sizes behind one load at the corpus frame at the engine's own budget, 166
  replies in **782.17 s** with none empty or capped, and every band held: `bare` carried the rule in
  **40 of 40** summaries at 16 px and **31 of 40** at 24 px, `bare` control applied it in **0 of
  40**, and `plain` control applied it in **38 of 40**. At 16 px the probe's control arm wrote the
  same string in all twenty draws that the square's sitting printed. Two things moved and neither is
  the reading: `bare` drew its first application ever, one of 40 framed draws, so the probe's zero is
  about the arm rather than about the screen; and `plain` framed came back 6 of 20 and 9 of 20 where
  the sweep drew 0 of 5 and 1 of 5, which agrees with the 37 of 117 the 120-draw row measured at this
  frame and budget and makes the sweep's two cells low draws. The row is the
  [ADR-0029 body-pair addendum](../../adr/ADR-0029-vision-screen-capture.md), three of its replies
  are now held to their hand sort in
  [test_reply_readings.py](../../../brain/packages/inference/tests/test_reply_readings.py), and the
  per-load settling it shows again is named in
  [623](623-a-cell-that-settles-per-load-is-read-in-draws-rather-than-loads.md).
