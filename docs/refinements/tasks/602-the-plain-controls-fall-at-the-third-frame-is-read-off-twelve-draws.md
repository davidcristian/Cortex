# The plain control's fall at the third frame is read off twelve draws

**Status:** landed 2026-09-08
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-09-07 by the close of
[R-597](597-the-third-frame-is-drawn-by-the-rate-row-alone.md), whose matrix at `4800x2700` drew
the one cell the sweep beside it reports at zero.

`plain/output-laundering` control at `4800x2700` at the engine's own budget has now been drawn in
three rows: 0 of 5 by the rate row, 0 of 5 at each of three payload sizes by the sweep, and 1 of 1
by the matrix, which was obeyed. So the control has applied the rule once in the twelve draws that
frame has had at the corpus payload size, where the same control applies it 4 times in 5 at the
corpus frame. The direction the frame axis rests on is unchanged and the number under it is not a
zero, which is what the third-frame addendum's reading of the misses assumed.

**Why it was left.** The sitting's depth went to the corpus frame at both budgets, where the entry
that asked for it was aimed, and this cell is a third frame's control arm.

**What would close it.** Draw `plain` alone at `4800x2700` at the engine's own budget at 120 per
arm, which also settles
[R-601](601-the-plain-framed-cell-at-the-third-frame-reads-1-of-5-and-4-of-5.md) on the same load,
and read the control's count against the corpus frame's 4 in 5. A count near 10 of 120 says the
frame takes the rule away from this control without silencing it; 0 of 120 says the twelve-draw
firing was the tail of a rate that really is at the floor. About twenty-five minutes of card time
for the two arms.

## Trail

- 2026-09-07: opened by the close of
  [R-597](597-the-third-frame-is-drawn-by-the-rate-row-alone.md), whose
  [ADR-0029 depth-at-both-budgets addendum](../../adr/ADR-0029-vision-screen-capture.md) publishes
  the matrix.
- 2026-09-08: **landed on this entry's own second branch: the control is silent in 120 draws.**
  Drawn as this entry asked, on one load with
  [601](601-the-plain-framed-cell-at-the-third-frame-reads-1-of-5-and-4-of-5.md): `plain` alone at
  `4800x2700` at the engine's own budget, 120 per arm, in 1869.04 s. The control applied the
  payload's rule in **0 of 120** draws and mentioned its token in none, where the same control at
  the corpus frame at this budget applies it in 119 of 120. Pooled with the twelve draws this frame
  had before tonight, the control has applied the rule once in 132 draws here, a rate under 4.1 in
  a hundred, so the matrix's one firing is the tail of a rate at the floor and no published reading
  of the frame axis moves. The 119 identical control replies name the formatting rule and stop
  before its token, which is what the count is read off rather than inferred from. The row is the
  [ADR-0029 two-pre-registered-rows addendum](../../adr/ADR-0029-vision-screen-capture.md).
