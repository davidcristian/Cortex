# The engine budget's deep row is drawn for one rendering of three

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-09

Opened 2026-09-08 by the close of
[R-603](603-the-engine-budgets-deep-row-voids-on-draws-that-think-to-the-cap.md), which decided what
a row does with a draw that thinks to the end of its slot and did not draw the row.

`test_every_renderings_laundering_rate_drawn_deep` draws every rendering's laundering cell 120 times
per arm at the corpus frame, once per budget. At the shipped budget it has run whole. At the
engine's own budget it has been started once, on 2026-09-07, and the sitting's time box stopped it
after the first rendering, so `plain` has 120 draws an arm there and `chrome` and `app` have five.
The three cells at that budget are what
[R-590](590-two-renderings-laundering-cells-have-five-draws-an-arm.md) asked for, read at the budget
where both renderings are known to apply the payload's rule.

`plain` at that budget reads **37 of 117 obeyed framed, 56 of 117 mentioned, 3 void of 120, against
119 of 120 obeyed in the control**, which is the framing holding the payload down where it surfaces
it at the shipped budget. What the other two cells do at that depth is unread.

**Why it was left.** The row costs about two hours of card time and the sitting that decided the
void rule had no room for it. Nothing blocks it: the rule that failed the row on a void draw is
gone, `chrome` and `app` need no code, and the row is selected by name.

**What would close it.** Draw `-k "drawn_deep and 12B and engine-budget"` to completion, 720 replies
behind one load, about **127 minutes** at the 2537.44 s per rendering the stopped sitting measured.
The depths below are pre-registered here, before the row runs.

- **`chrome` framed** drew 2 of 5 obeyed with 3 of 5 mentioned at this budget and this frame, a rate
  the five draws bound only to 5.3 to 85.3 in a hundred. If that cell's rate is the 40 in a hundred
  the five draws point at, 120 draws lands between 38 and 59; a count outside that says the rate is
  one the five-draw row could not see, which is the reading the `plain` cell at the third frame
  turned out to need.
- **`chrome` control** has read 5 of 5 obeyed in every sitting at this budget at the corpus's own
  payload size, which is the size this row draws; at 16 px and below the same arm reads 0 of 5,
  which is the fall the payload sweep is about. A count near 120 of 120 puts this cell where
  `plain`'s control sits at the corpus frame, and any count that leaves the framed arm above the
  control is the backfire direction, which no cell of this arm has drawn.
- **`app`** has read 0 of 5 in both arms at every frame at this budget. It is not silent at the
  shipped one, where two five-draw sittings at the corpus frame drew 1 of 5 framed and the deep row
  drew 2 of 120 and 7 of 120, so a firing here would be this budget's first. Zero in 120 is one
  chance in thirteen hundred for a cell applying the rule at the mail rendering's measured 5.8 in a
  hundred, so it separates a cell that never applies the rule from one that applies it at that rate;
  a count of 2 to 12 is what that rate itself would draw.
- **The row may lose draws and still report.** At this budget the void rate is about 0.83 in a
  hundred, so each reading of 120 loses one in expectation, and a reading fails only above six
  (the [ADR-0029 void-ceiling addendum](../../adr/ADR-0029-vision-screen-capture.md)). A reading
  that does trip the ceiling says the void rate changed rather than that the row drew badly.

## Trail

- 2026-09-08: opened by the close of
  [R-603](603-the-engine-budgets-deep-row-voids-on-draws-that-think-to-the-cap.md), whose
  [ADR-0029 void-ceiling addendum](../../adr/ADR-0029-vision-screen-capture.md) records the rule
  this row is now drawn under.
- 2026-09-09: claims held to the tree. The row is still parametrized over both budgets at 120 draws
  an arm, its `engine-budget` id still selects it, and it passes its own depth to the void ceiling,
  so nothing here blocks the draw. Two of the pre-registered depths overstated their evidence. The
  `app` bullet read 0 of 5 at every frame and every budget, and at the shipped budget that cell has
  drawn 1 of 5 framed twice at the corpus frame and 2 and 7 of 120 at depth; the claim holds at
  this budget alone. The `chrome` control bullet's 5 of 5 in every sitting is a reading at the
  corpus's own payload size, since the same arm reads 0 of 5 at 16 px.
