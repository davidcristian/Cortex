# A cell that settles per load is read in draws rather than loads

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-09-10 by the close of
[R-604](604-the-advisory-probes-arms-part-by-fourteen-draws.md), which drew the advisory probe's two
arms a third time and found the control arm at the opposite end from the second time.

Every deep row in the image arm draws its depth behind one load: `_draw_deep_cell` takes the client
from its caller, and the caller holds one `_server` for the whole row. So a row of 560 draws is 560
draws of one load, and what it measures precisely is the answer that load settled on.

On the `advisory` probe at 16 px, at the corpus frame at the engine's own budget, the settling is
the whole of the reading. Three loads drew that cell's control arm at 4 of 5, 1 of 20 and 19 of 20,
and in each of the two deep loads the control drew one string 19 times in 20. The strings differ
between the loads. Depth inside a load cannot see that spread, so the 14 draws the second load's
arms parted by were a property of that load.

It is not every cell. The `plain` cell drew 42 distinct strings in 560 framed draws at the shipped
budget, from a prompt that does not change, while its control drew one string 560 times. So the
settling is per arm and per cell, and a row that spent its card time on depth where the cell settles
bought one sample at high precision.

**Why it was left.** R-604 was asked which of two published readings of one cell replicates, and a
third load answers that. Drawing a cell across loads is a row shape this arm does not have: every
deep row here holds one server for its whole depth, and a row that restarts the server between
blocks has to be written and its blocks read against each other rather than pooled.

**What would close it.** Add a row that draws one cell across several loads rather than one, say
four loads of twenty per arm on one rendering, restarting the server between blocks and printing a
count per load beside the total, so a cell's between-load spread is a number rather than an
inference from two sittings. Then say which readings need it, which is the cell whose arm draws one
string in most of its draws, since that is what the settling looks like in the printed replies. At
this cell's cost the row is about eleven minutes: this sitting drew 84 replies behind one load in
301.47 s, roughly 3.2 s a reply with about 30 s for the load.

## Trail

- 2026-09-10: opened by the close of
  [R-604](604-the-advisory-probes-arms-part-by-fourteen-draws.md), whose
  [ADR-0029 advisory-control addendum](../../adr/ADR-0029-vision-screen-capture.md) publishes the
  three loads and the strings each settled on.
- 2026-09-10: a second cell and the other candidate. The cortex alt's `chrome` cell at the corpus
  frame at the shipped budget drew twenty per arm behind one load: the control arm wrote one string
  in all twenty draws and the framed arm two near-identical strings, 15 and 5, where the same cell's
  five-draw row had drawn 3 of 5 on the mention reading. So the settling is not the probe's, and the
  row shape this entry asks for is what a reading of either candidate's dialog cell needs
  ([ADR-0029's alt-spelling addendum](../../adr/ADR-0029-vision-screen-capture.md)).
- 2026-09-10: and the square's other pair, in the same shape. Drawing `bare` and `plain` twenty per
  arm at 24 px and at 16 px behind one load, the control arm wrote one string in all twenty draws in
  two of the four cells and two strings in the other two, while the framed arm wrote 19 distinct
  strings in one cell and 2 in another. So the arm that settles is the arm that agrees with itself,
  and the between-load spread this entry asks for is what any control reading of these cells needs
  ([ADR-0029's body-pair addendum](../../adr/ADR-0029-vision-screen-capture.md)).
