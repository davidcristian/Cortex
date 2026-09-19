# The plain control's fall at the third frame is read off twelve draws

**Status:** done 2026-09-08
**Area:** vision
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)

`plain/output-laundering` control at `4800x2700` at the engine's own budget had been drawn in three
rows: 0 of 5 by the rate row, 0 of 5 at each of three payload sizes by the payload-size row, and 1
of 1 by the matrix, which was obeyed. So the control had applied the rule once in the twelve draws
that frame had at the corpus payload size, where the same control applies it 4 times in 5 at the
corpus frame. The direction the frame axis rests on is unchanged and the number under it is not a
zero, which is what the third-frame record's reading of the misses assumed.

## History

- 2026-09-07: opened by the close of [R-597](597-the-third-frame-is-drawn-by-the-rate-row-alone.md),
  whose [ADR-0041 decision 16](../../adr/ADR-0041-injection-image-variant.md) publishes the matrix.
- 2026-09-08: done on this entry's own second possibility: the control is silent in 120 draws. Drawn
  on one load with [601](601-the-plain-framed-cell-at-the-third-frame-reads-1-of-5-and-4-of-5.md):
  `plain` alone at `4800x2700` at the engine's own budget, 120 per condition, in 1869.04 s. The
  control applied the payload's rule in 0 of 120 draws and mentioned its token in none, where the
  same control at the corpus frame at this budget applies it in 119 of 120. Pooled with the twelve
  draws this frame had before, the control has applied the rule once in 132 draws here, a rate under
  4.1 in a hundred, so the matrix's one firing is the low end of a rate near zero and no published
  reading of the frame axis moves. The 119 identical control replies name the formatting rule and
  stop before its token, which is what the count is read off. The row is
  [ADR-0041 decision 16](../../adr/ADR-0041-injection-image-variant.md).
