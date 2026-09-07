# The third frame is drawn by the rate row alone, and the payload sweep still knows two frames

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-09-07 by the close of
[577](577-the-frame-gap-at-the-engines-budget-rests-on-two-points.md), which drew the laundering
rate at `4800x2700` and found the `plain` control's fall complete there.

`4800x2700` reaches the model through two rows: `test_the_laundering_rate_at_a_third_frame`, which
draws the one unstable cell at the engine's own budget, and the cost row, which measures what one
screen costs there at both budgets. The matrix row and the payload-size sweep still run at the two
frames in `FRAMES`, which was the deliberate scope of that close: a third entry in the parametrize
axis would have added a matrix, a sweep and a cost row per budget, hours of card time answering
nothing that had been asked.

One of the two now has a question behind it. The fall is on the rendering whose payload is
unstyled body text and on neither of the other two, and the instrument that varies a payload's own
size on the screen is the sweep, which has never been run at the frame where the fall is complete.
If the `plain` control's fall at `4800x2700` is about how much of the picture the payload holds
after the encoder's resample, the sweep at that frame should show the other renderings falling as
their payloads are set smaller. If it is about the resample alone, the sweep should look like the
sweep at the other two frames with `plain` already at the floor.

The matrix row's question is smaller: the nine attacks other than `output-laundering` have been
drawn at two frames and would be drawn at a third, which is one more reading of cells that have
been stable across every frame so far.

**What would close it.** Draw the sweep at `4800x2700` at the engine's own budget, as a row of its
own beside the third-frame rate row or by giving the sweep its own frame argument, and read the
three renderings' rates against the same sweep at the corpus frame. About six minutes of card time
by the sweep's own published cost. The matrix at the third frame is a separate call and need not
be made in the same sitting.

## Trail

- 2026-09-07: opened by the close of
  [577](577-the-frame-gap-at-the-engines-budget-rests-on-two-points.md), whose
  [ADR-0029 third-frame addendum](../../adr/ADR-0029-vision-screen-capture.md) publishes the three
  frames' rate rows and the third frame's image-token cost.
