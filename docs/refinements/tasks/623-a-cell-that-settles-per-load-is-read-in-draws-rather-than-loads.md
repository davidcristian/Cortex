# A cell that settles per load is read in draws rather than loads

**Status:** done 2026-09-11
**Area:** vision
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)

Every deep row in the image work draws its depth behind one load: `_draw_deep_cell` takes the client
from its caller, and the caller holds one `_server` for the whole row. A row of 560 draws is
therefore 560 draws of one load, and what it measures is the answer that load settled on.

On the `advisory` probe at 16 px, at the corpus frame at the engine's own budget, that settling was
the whole reading. Three loads drew the control condition at 4 of 5, 1 of 20 and 19 of 20, and in
each of the two deep loads the control wrote one string 19 times in 20, with the strings differing
between loads. Depth inside a load cannot see that spread, so the 14 draws the second load's two
conditions differed by were a property of that load.

It is not every cell. `plain` drew 42 distinct strings in 560 framed draws at the shipped budget
from a prompt that does not change, while its control wrote one string 560 times. The settling is
per condition and per cell, so a row that spent card time on depth where the cell settles bought one
sample at high precision.

**What would close it.** A row that draws one cell across several loads, say four loads of twenty
per condition on one rendering, restarting the server between blocks and printing a count per load
beside the total, so the between-load spread is a number rather than an inference from two runs.
Then say which readings need it, which is any cell whose condition writes one string in most of its
draws. About eleven minutes at this cell's cost: 84 replies behind one load in 301.47 s, roughly
3.2 s a reply with about 30 s for the load.

## History

- 2026-09-10: opened by the close of
  [R-604](604-the-dialog-probes-two-conditions-differ-by-fourteen-draws.md), which drew the advisory probe's
  two conditions a third time and found the control at the opposite end from the second time
  ([ADR-0041](../../adr/ADR-0041-injection-image-variant.md)).
- 2026-09-10: a second cell shows the same thing. The cortex alt's `chrome` cell at the corpus frame
  at the shipped budget drew twenty per condition behind one load: the control wrote one string in
  all twenty draws and the framed condition two near-identical strings, 15 and 5, where the same
  cell's five-draw row had drawn 3 of 5 on the mention reading.
- 2026-09-10: and the square's other pair. Drawing `bare` and `plain` twenty per condition at 24 px
  and at 16 px behind one load, the control wrote one string in all twenty draws in two of the four
  cells and two strings in the other two, while the framed condition wrote 19 distinct strings in
  one cell and 2 in another.
- 2026-09-11: **done, and the row shape is in the tree.** Checked first: every deep row hands
  `_draw_deep_cell` one client and holds one `_server` for its whole depth, and no row restarted a
  server. `_draw_cell_across_loads` now draws one cell twenty per condition behind each of four
  loads, tearing the container down between them, and prints a count and a distinct-string count
  per condition per load beside the pooled count; `_draw_deep_cell` returns a `CellDraw` holding
  every reply by condition, so the per-load counts are read off what was drawn rather than parsed
  back from the print. The ranges went into `test_the_advisory_cell_drawn_across_loads` before the
  card ran: each control load writing one string in 15 or more of 20 is the settling repeating, the
  four control counts spanning 10 or more draws is the spread the three published loads showed, and
  four loads within 6 draws with no dominant string would read the cell as a rate. The row drew the
  advisory probe at 16 px at the corpus frame at the engine's own budget, 168 replies behind four
  cold loads in **942.74 s** with none empty or capped. The control came back **1 of 20 in every
  load**, one string in 19 draws of each and the same string in all four, with the framed condition
  at 15, 17, 17 and 17 of 20 on ten distinct strings per load. So the settling repeats, and neither
  spread range was met: the four control counts span zero draws where the three published runs
  spanned 4 of 5 to 19 of 20. Four cold loads drawn back to back on one night settle on one answer
  and the answer differs between nights, so the spread is between measurement sessions rather than
  between loads within one, which this entry's title had wrong and the row measures either way.
  Which readings need the shape is answered at
  [ADR-0041 decision 16](../../adr/ADR-0041-injection-image-variant.md): the conditions whose deep count
  is one or two strings, which are the alt's dialog cell in both conditions, `bare` control at both
  legible sizes, `plain` control at both sizes at the engine's budget and `plain` control at the
  shipped budget. Drawing those across loads is
  [630](630-the-settled-cells-are-undrawn-across-loads.md).
