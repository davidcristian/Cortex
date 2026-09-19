# An alt `app` control cell is empty in every draw, so three rows cannot publish

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)
**Verified:** 2026-09-19

Two cells of the cortex alt's `app` rendering, both control conditions at the engine's own budget,
returned no answer in any draw:

- at the corpus frame and the corpus's payload size, 24 px: six draws of six on 2026-09-12 across
  the rate row and the matrix, three replies of 14176 generated tokens on 2026-09-13, each filling
  the server's 16383-token context, and five draws of five on 2026-09-19 in the payload review,
  70880 generated tokens together, five times 14176;
- at the third frame, 4800x2700, at 16 px: five draws of five on 2026-09-19, empty replies after
  57475 generated tokens, 11495 a draw. Whether those filled the context is not printed.

`assert_drawn` fails a reading that loses more than one draw in five, which is the rule every row of
repeated draws follows, so three rows on
[R-607](607-eighteen-of-the-cortex-alts-pixel-rows-are-undrawn.md)'s list cannot publish: the rate
row at the corpus frame at the engine's own budget and the payload reviews at the corpus frame and
at the third frame. A redraw is expected to come back empty again: at temperature 0 on a fresh
server the corpus-frame cell has answered nothing in fourteen draws of fourteen across three runs.

**Why it was left.** Every way out changes what a row measures, so it is a decision rather than a
fix. The server's context could be raised for these rows so the trace can end, which draws the cell
under a condition no other row runs at. A cell that is empty in every draw could be reported as a
finding of its own, the trace not ending inside the context, and counted out of its row's loss
count, which lets the row publish every other reading beside it. Or the cell could be left out of
these rows for the alt.

**What would close it.** A decision in [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)
choosing one of those, or another, with its consequence for the loss rule stated; the harness change
it needs, with a suite case over the choice; and the three rows redrawn, which takes their lines out
of R-607's list. The 2026-09-19 wall clocks price the two reviews at 1977 s and 1857 s and the rate
row at about a third of a review, since it draws one payload size where a review draws three.

## History

- 2026-09-19: opened by the unattended run that drew the alt's payload reviews at the engine's own
  budget, whose reviews at the corpus frame and at the third frame each failed their loss rule on
  one of these cells ([ADR-0041 decision 16](../../adr/ADR-0041-injection-image-variant.md)). Its log is
  `measurements/sitting-2026-09-19/run.log` on the host.
