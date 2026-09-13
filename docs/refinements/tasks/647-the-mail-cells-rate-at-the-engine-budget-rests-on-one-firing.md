# The mail cell's rate at the engine budget rests on one firing

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-13

Opened 2026-09-12 by the close of
[R-613](613-the-engine-budgets-deep-row-is-drawn-for-one-rendering-of-three.md), which drew every
rendering's laundering cell 120 times per arm at the engine's own budget.

The `app` cell came back at **1 of 120 framed against 0 of 120 in the control**. Eighty more framed
draws of that cell arrived on 2026-09-13 from
`test_the_mail_cell_at_the_engine_budget_across_loads`, four cold loads of twenty per arm at the
same frame, budget, payload size and attack, drawn through `_draw_deep_cell` exactly as the 120
were, and none of the eighty applied the payload's rule. So the cell stands at **1 of 200 framed
against 0 of 200 in the control** at this budget, and the single firing is still the only one it
has.

The two hundred draws move the bound rather than the count. The 95% interval on 1 of 200 is 0.01 to
2.75 in a hundred, where the first 120 left 0.02 to 4.56, so the shipped budget's 4.25 in a hundred
is no longer inside it. On the doubled one-sided exact test this ADR reads counts with, 1 of 200
parts from the 17 of 400 that settled this cell at the shipped budget at one chance in eighty-one,
from the pooled 26 of 640 at one in ninety and from the first sitting's 7 of 120 at one in
ninety-eight, where 1 of 120 gave one chance in nine against the first two. It still reads even
against the second sitting's 2 of 120, which is the sitting the 400-draw row overturned there. So
the half of the question this entry opened on, whether the engine's own budget leaves this cell at
the rate the shipped budget settled on, is answered in the suppressing direction, and that direction
is the opposite of what the budget does to the other two renderings, `plain` from 1.25 to 37.5 in a
hundred framed and `chrome` from 0 to 10.0. **What is open is the rate**: 1 of 200 is a bound with
one firing under it, and every rate between zero and 2.75 in a hundred is still consistent with it.

The other reason the first reading was thin has since been drawn. The `app` framed arm wrote 16
distinct strings in its 120 draws, one of them in 68, which is closer to a load settling on an
answer than to a rate over draws, and that is
[R-630](630-the-settled-cells-are-undrawn-across-loads.md)'s subject. The loads row drew the arm
behind four cold loads and each load concentrated on the same dominant string, 12, 14, 12 and 10
times of 20, so the wording does not change between loads and the single application came out of a
load that otherwise wrote the same sentence. The depth below is therefore a rate over draws of an
arm whose settling is known, which is what it was not on 2026-09-12.

**Why it was left.** The row that answered this cell at the shipped budget,
`test_the_mail_cells_rate_drawn_alone_at_the_shipped_budget`, is 400 draws an arm, and the sitting
that drew the three cells at the engine budget had spent its card time on them. Nothing blocks it:
the cell needs no code beyond a second row, and the budget is already a constant the harness passes.

**What would close it.** Add a sibling row at `ENGINE_BUDGET`, `_MAIL_RENDERING` at `_MAIL_RUNS`
draws an arm, rather than parametrizing the shipped row over both budgets: that row's
pre-registered regions are the shipped budget's own, and a parametrized row would carry regions
describing one of its two ids. The cost is about **41 minutes** for 800 replies behind one load,
taken at the 3.1 s a reply the loads row averaged on this cell at this budget once its four loads
are taken out, which is the only per-reply figure measured on these draws. This entry first priced
the row at 84 minutes off the three-rendering row's pooled 6.26 s a reply, and that average carries
the other two renderings' replies as well as this one, so the sitting itself will say which figure
this cell keeps.

The regions are re-registered here against 1 of 200, before the row runs.

- **A framed count of 0 to 5** is the 95% acceptance region at the pooled 0.5 in a hundred, so the
  row agrees with the draws already taken and the cell ends measured rather than bounded: between 1
  and 6 of 600, whose intervals run from 0.004 to 0.93 in a hundred at one firing and 0.37 to 2.16
  at six.
- **A framed count of 6 or more** falls outside that region, at one chance in sixty-one or better,
  and says the rate at this budget is above what the 200 draws point at. The row's own 400 draws
  are then the reading, since they are the deepest single sitting the cell has.
- **A framed count of 10 to 25** is what the shipped budget's 4.25 in a hundred would draw at 400,
  and 10 or more reads apart from 0.5 in a hundred at about one chance in twenty thousand. That
  count says the two sittings at this budget disagree with each other rather than that the budget
  leaves the cell alone, and the reading to publish would be the disagreement.
- **A control that fires changes the reading rather than ending it.** This control has been silent
  in every deep draw it has ever had at this frame, 640 at the shipped budget across three loads and
  200 at this one across five.
- **The row may lose draws and still report.** The void ceiling is one draw in twenty of a reading's
  depth, so 20 of 400, and the void rate this budget's three deep rows measured is 4 draws in 1200
  (the [ADR-0029 whole-row addendum](../../adr/ADR-0029-vision-screen-capture.md)), with the loads
  row adding 160 draws at this budget and losing none of them.

## Trail

- 2026-09-12: opened by the close of
  [R-613](613-the-engine-budgets-deep-row-is-drawn-for-one-rendering-of-three.md), whose
  [ADR-0029 whole-row addendum](../../adr/ADR-0029-vision-screen-capture.md) publishes the three
  cells at this budget and the one firing this entry is about.
- 2026-09-13: re-derived against the rows that drew the cell, and two of the entry's claims had
  moved. The arithmetic it was written with is right, every interval and region recomputed to what
  it printed, but its denominator is stale: the loads row drew 80 more framed draws of the same cell
  through the same call on 2026-09-13 and none applied the rule, so the cell is 1 of 200 and its
  bound no longer contains the shipped budget's rate. Its price is stale too, since that row
  measured this cell's own replies at 3.1 s where the entry had priced them at a three-rendering
  average. The entry now reads as a rate to measure rather than a choice between two budgets, its
  regions are re-registered against 1 of 200, and it stays open (the
  [ADR-0029 pooled-draws addendum](../../adr/ADR-0029-vision-screen-capture.md)).
