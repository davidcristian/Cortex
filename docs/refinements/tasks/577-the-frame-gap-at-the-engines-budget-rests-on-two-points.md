# The frame gap at the engine's budget rests on two points, and it is on one rendering

**Status:** open, actionable
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
