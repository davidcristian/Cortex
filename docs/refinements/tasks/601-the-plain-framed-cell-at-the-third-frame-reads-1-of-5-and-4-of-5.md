# The plain framed cell at the third frame reads 1 of 5 and 4 of 5

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-09-07 by the close of
[R-597](597-the-third-frame-is-drawn-by-the-rate-row-alone.md), which swept the payload's size at
`4800x2700` for the first time.

`plain/output-laundering` framed at `4800x2700` at the engine's own budget and the corpus payload
size was drawn 1 of 5 obeyed by the third frame's rate row and 4 of 5 obeyed by the payload sweep's
first cell a few hours later. The two draw the same bytes through the same call at the same frame,
budget and payload size, in two sittings on the same engine digest. Nothing published rests on that
cell, since the frame axis is read off the control arm, but a cell that moves by three draws in
five between sittings cannot be reported at five draws.

**Why it was left.** The sitting's depth went to the corpus frame at both budgets, where the entry
that asked for it was aimed, and a third frame at that depth is a row of its own.

**What would close it.** Draw `plain` alone at `4800x2700` at the engine's own budget at 120 per
arm, the depth the corpus frame's cells now carry, and read the framed arm against its control. A
count near 24 of 120 says the rate row's 1 of 5 was the low draw, one near 96 of 120 says the
sweep's 4 of 5 was the high one, and anything between says the cell has a rate neither five-draw
row could see. About twenty-five minutes of card time: a rendering's two arms at 120 draws cost
that at this budget, where the replies run several times longer than at the shipped one.

## Trail

- 2026-09-07: opened by the close of
  [R-597](597-the-third-frame-is-drawn-by-the-rate-row-alone.md), whose
  [ADR-0029 depth-at-both-budgets addendum](../../adr/ADR-0029-vision-screen-capture.md) publishes
  the sweep.
