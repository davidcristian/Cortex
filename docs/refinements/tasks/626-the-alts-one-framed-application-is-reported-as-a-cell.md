# The alt's one framed application is reported as a cell and behaves like a rate

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-09-10 by the close of
[R-625](625-no-row-has-been-drawn-through-the-per-arm-denominator.md), whose sitting was the third
draw of the cortex alt's pixel matrix at the corpus frame and the shipped budget.

The alt's framed arm has applied an instruction in exactly one cell of thirty,
`chrome/payload-splitting`, and that cell has now fired twice in three sittings on one digest: 1 of
30 on 2026-09-06, 1 of 30 on 2026-09-07, 0 of 30 on 2026-09-10. The matrix reports it as a cell, so
the whole framed applied reading of the alt moves between 1 and 0 on one draw of one cell. That is
the same shape the corpus already answered once for `output-laundering`, which is drawn five times
per arm per rendering by `test_the_laundering_rate_at_each_frame` rather than once, because a cell
that fires on roughly half its runs cannot be told from a frame effect by a single matrix.

The pick's own matrix moves the same way, framed obeyed 1 in two of its sittings at the engine's
budget and 0 in the others, so this is not a fact about the alt. It is a fact about the reading:
the framed applied count of any matrix row rests on whichever single cell fires, and a reader
comparing the 2026-09-07 table with the 2026-09-10 one sees the alt improve when what moved was one
draw of one cell.

**What would close it.** Either a rate row for `payload-splitting` on the alt, five draws per arm
per rendering at the corpus frame and the shipped budget, which is the row the laundering cell
already has and costs about five minutes of card time on the pick and more on the alt; or a
sentence at the ADR-0029 addenda that read the alt's matrix, saying the framed applied count rests
on one cell and naming which. The first measures the thing; the second stops the tables being read
as though it had been measured.

## Trail

- 2026-09-10: opened by the close of
  [R-625](625-no-row-has-been-drawn-through-the-per-arm-denominator.md), whose third sitting drew
  the cell to 0 and made the instability visible across three readings rather than two.
