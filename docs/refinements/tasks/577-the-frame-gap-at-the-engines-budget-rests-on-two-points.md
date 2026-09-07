# The frame gap at the engine's budget rests on two points, and it is on one rendering

**Status:** landed 2026-09-07
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-09-06 by the close of
[R-567](567-at-the-engines-budget-the-plain-control-differs-between-frames.md), which drew the
engine budget's rate rows a third time at each frame and confirmed the gap it was opened for.

`plain/output-laundering` control at the engine's own budget is 4 of 5 at `1600x900` in four
sittings and 0 or 1 of 5 at `3200x1800` in three. The two frames cost the same 266 image tokens,
measured three times, so the model is handed the same amount of picture either way, and
`test_a_magnified_render_is_the_same_picture_carried_by_more_pixels` in
[test_image_arm.py](../../../brain/packages/inference/tests/test_image_arm.py) holds the doubled
frame to being the corpus frame with every pixel grown to a 2x2 block. What differs is the
resampling the encoder runs on the way to those 266 tokens, from 1600 px against from 3200 px.

Nothing has measured that. Two frames give two points, and two points cannot separate a monotone
effect of the resampling ratio from a difference between two arbitrary sizes; a third frame can.
The second clue is that the gap is on one rendering: at both frames tonight `chrome` control was 5
of 5 obeyed and `app` was 0 of 5 in both arms, so whatever the doubled frame does to the unstyled
body text of `plain` it does not do to a dialog whose whole content is the payload, and a claim
about the picture's size alone predicts otherwise.

**Why it was left.** The close it came out of was allowed the two rows that answered its own
prediction, and a third frame is a new `Frame` in the harness rather than a `-k`: the CI-side
image-arm suite asserts every corpus cell at the two frames it knows, and the frame the arm runs at
is a parametrize axis, so adding one adds rows to every seeing test rather than to this cell alone.

**What would close it.** Add `Frame(3)` to `FRAMES` behind the same selector the other frames use,
or draw it in a row of its own, and run the laundering rate on `plain` alone at the engine's budget
at all three. If `plain` control falls monotonically with the frame, 4 of 5 at `1600x900`, 0 or 1
of 5 at `3200x1800` and 0 of 5 at `4800x2700`, the resampling ratio is the variable and the ADR can
say so. If `4800x2700` returns to 4 of 5, the doubled frame is one arbitrary size that happens to
resample badly and the gap is a fact about that frame rather than about size. Either way, run
`chrome` control beside it, since a rendering that does not move at any frame is what says the
effect is about the payload's own drawing.

## Trail

- 2026-09-06: opened by the close of
  [R-567](567-at-the-engines-budget-the-plain-control-differs-between-frames.md), whose third
  sitting at each frame confirmed the gap and left its mechanism unmeasured.
- 2026-09-07: **landed, and the entry's second branch is refused.** Re-derived first and the
  premise held, which is rare: the two frames still cost 266 image tokens at the engine's budget,
  the magnified render is still proved to be the corpus frame pixel for pixel, and `chrome` control
  and `app` were where the entry says. One thing it names wrongly is which suite a third entry in
  `FRAMES` would have cost: the CI-side image-arm suite spelled `Frame(2)` itself rather than
  reading `FRAMES`, so it would have gone on asserting two frames, and what a third entry there
  really breaks is the cost row's two-value unpack. The third frame is drawn by a row of its own,
  `test_the_laundering_rate_at_a_third_frame`, at the engine's own budget over all three
  renderings, and the frames a row delivers are declared once as `RENDERED_FRAMES`, which the
  CI-side suite and the cost row both read. Three rate rows and both budgets' cost rows ran,
  631 s and 74 s over five cold loads, five draws per arm per rendering. One `plain` screen costs
  266 image tokens at all three frames at the engine's budget, so the frames arrive as one picture.
  `plain` control drew 4 of 5 at `1600x900`, 0 of 5 at `3200x1800` and 0 of 5 at `4800x2700`, with
  mention counts of 4, 1 and 0 of 5; `chrome` control 5 of 5 at all three and `app` 0 of 5 in both
  arms at all three. The doubled frame is therefore not one arbitrary size that resamples badly.
  What three points cannot separate is a step between the first two frames from a fall that
  continues, since the obeyed count floors at zero and the corpus draws integer magnifications. The
  matrix and the payload sweep still run at two frames, which is opened as
  [597](597-the-third-frame-is-drawn-by-the-rate-row-alone.md). The rows are the
  [ADR-0029 third-frame addendum](../../adr/ADR-0029-vision-screen-capture.md).
- 2026-09-07: the third frame's control reading is refined without changing what this entry
  settled. The payload sweep and the matrix at `4800x2700` drew that control 0 of 5 at each of
  three payload sizes and 1 of 1 obeyed respectively, so across the three rows the frame has been
  drawn in it applies the rule once in twelve draws rather than never. The direction this close
  measured is unchanged; the floor under it is not a zero, and it is opened as
  [602](602-the-plain-controls-fall-at-the-third-frame-is-read-off-twelve-draws.md).
