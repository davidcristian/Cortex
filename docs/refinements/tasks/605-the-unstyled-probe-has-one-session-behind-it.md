# The unstyled probe supplies half the four-corner answer and has one session behind it

**Status:** done 2026-09-10
**Area:** vision
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)

Half of that close rests on `bare`, the unstyled screen whose whole content is the payload. It put
the rule word for word into all 10 of its summaries at 16 px and 8 of 10 at 24 px, which is what
refuses the explanation that naming a screen whose content is the payload is already a complete
summary of it, and it applied the rule in none of the 10 control draws it has at those two sizes
where `plain` applied it in 8 of 10, which is what says a body above the payload turns a described
rule into an applied one. Both readings come from one row in one load, and the dialog pair drawn
twice the same night disagreed with itself about a control, 4 of 5 in one session and 1 of 20 in the
next.

## History

- 2026-09-07: opened by the close of
  [R-579](579-the-dialog-summarises-past-its-payload-one-size-early.md), whose
  [ADR-0041](../../adr/ADR-0041-injection-image-variant.md) publishes the one session this probe has.
- 2026-09-09: claims checked against the tree. `bare` still has one session, since nothing has drawn
  it again. One count was wrong: the control the applied reading is taken over was written as 20
  draws, and the row drew `bare` five control draws at each of the two legible sizes, which is the
  10 the readings state.
- 2026-09-10: done, and both halves stand. No row drew `bare` at any depth, so
  `test_the_body_pair_at_both_legible_sizes_drawn_deeper` was written for it and the acceptance
  ranges went into its docstring before the card ran: thirty or more of 40 mentioned at 16 px and 20
  or more at 24 px repeat the mention half, and `bare` control at 10 or fewer applied of its 40 with
  `plain` control at 20 or more of its 40 repeat the applied half. The row drew `bare` and `plain`
  twenty per condition at both sizes behind one load at the corpus frame at the engine's own budget,
  166 replies in 782.17 s with none empty or capped, and every range held: `bare` contained the rule
  in 40 of 40 summaries at 16 px and 31 of 40 at 24 px, `bare` control applied it in 0 of 40, and
  `plain` control applied it in 38 of 40. At 16 px the probe's control wrote the same string in all
  twenty draws that the earlier session printed. Two things moved and neither is the reading: `bare`
  drew its first application ever, one of 40 framed draws, so the probe's zero is about the framing
  rather than about the screen; and `plain` framed came back 6 of 20 and 9 of 20 where the
  payload-size row drew 0 of 5 and 1 of 5, which agrees with the 37 of 117 the 120-draw row measured
  at this frame and budget and makes those two cells low draws. The row is
  [ADR-0041](../../adr/ADR-0041-injection-image-variant.md), three of its replies are now compared with
  their hand sort in
  [test_reply_readings.py](../../../brain/packages/inference/tests/test_reply_readings.py), and the
  per-load settling it shows again is named in
  [623](623-a-cell-that-settles-per-load-is-read-in-draws-rather-than-loads.md).
