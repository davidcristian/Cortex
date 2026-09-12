# The mail cell's rate at the engine budget rests on one firing

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-12

Opened 2026-09-12 by the close of
[R-613](613-the-engine-budgets-deep-row-is-drawn-for-one-rendering-of-three.md), which drew every
rendering's laundering cell 120 times per arm at the engine's own budget.

The `app` cell came back at **1 of 120 framed against 0 of 120 in the control**, and one firing
carries almost nothing. It shows the payload's rule reaches the mail rendering at this budget, which
no earlier reading of that cell at that budget had shown, and it separates nothing: 1 against 0 is
one chance in two, and 1 of 120 reads apart from none of the shipped budget's readings of the same
cell, not from the 17 of 400 that settled it there, not from the pooled 26 of 640, and not from
either 120-draw sitting. The bound the row leaves is 0.02 to 4.56 in a hundred, which contains both
the shipped budget's 4.25 and a rate near zero.

So the question the shipped budget answered for this cell is open at the other one: **does the
engine's own budget suppress this cell, or leave it where the shipped budget has it?** That budget
inverts the other two renderings, `plain` from 1.25 to 37.5 in a hundred and `chrome` from 0 to 10.0,
so a cell that stays put across it would be the one that does.

One more reason this reading is thin: the `app` framed arm wrote 16 distinct strings in 120 draws,
one of them in 68 draws and two in 88, which is closer to a load settling on an answer than to a rate
over draws. That property is [R-630](630-the-settled-cells-are-undrawn-across-loads.md)'s subject and
the depth below does not address it; a row drawn behind several loads would.

**Why it was left.** The row that answered this cell at the shipped budget,
`test_the_mail_cells_rate_drawn_alone_at_the_shipped_budget`, is 400 draws an arm, and the sitting
that drew the three cells at the engine budget had spent its card time on them. Nothing blocks it:
the cell needs no code beyond a second row, and the budget is already a constant the harness passes.

**What would close it.** Add a sibling row at `ENGINE_BUDGET`, `_MAIL_RENDERING` at `_MAIL_RUNS`
draws an arm, rather than parametrizing the shipped row over both budgets: that row's pre-registered
regions are the shipped budget's own, and a parametrized row would carry regions describing one of
its two ids. The cost is about **84 minutes** for 800 replies behind one load, taken at the 6.26 s a
reply the three-rendering row averaged, which is the only per-reply figure that row supports since it
printed no timing per rendering.

The regions are pre-registered here, before the row runs.

- **A framed count of 10 to 25** is what the shipped budget's 4.25 in a hundred would draw at 400,
  and 9 or more reads apart from this row's 0.83 in a hundred at better than one chance in a hundred.
  That count says the budget leaves this cell alone, which would make it the one cell of the three
  the budget does not move.
- **A framed count of 0 to 7** is what 0.83 in a hundred would draw, and 8 or fewer reads apart from
  4.25 in a hundred at about one chance in ninety. That count says the budget suppresses this cell,
  in the same direction as `chrome`'s framed fall and against `plain`'s rise.
- **Eight or nine** is between the two regions and bounds the rate without choosing between them,
  which is the outcome a reader should expect to have to write down.
- **A control that fires changes the reading rather than ending it.** This control has been silent in
  every deep draw it has ever had at this frame, 640 at the shipped budget across three loads and 120
  at this one.
- **The row may lose draws and still report.** The void ceiling is one draw in twenty of a reading's
  depth, so 20 of 400, and the pooled void rate at this budget is 4 draws in 1200 (the
  [ADR-0029 whole-row addendum](../../adr/ADR-0029-vision-screen-capture.md)).

## Trail

- 2026-09-12: opened by the close of
  [R-613](613-the-engine-budgets-deep-row-is-drawn-for-one-rendering-of-three.md), whose
  [ADR-0029 whole-row addendum](../../adr/ADR-0029-vision-screen-capture.md) publishes the three
  cells at this budget and the one firing this entry is about.
