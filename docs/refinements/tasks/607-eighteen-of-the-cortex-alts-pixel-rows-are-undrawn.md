# Twenty of the cortex alt's thirty-one pixel rows are undrawn or refused

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-12

Opened 2026-09-07 by the close of
[R-586](586-the-cortex-alts-pixel-rows-are-undrawn-now-that-its-artifact-loads.md), which drew the
alt's rate, matrix, cost and canary rows at the corpus frame.

Every row of the image arm in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
is parametrized over `VISION_MODELS`, which carries the pick and the alt. Collecting the arm on
2026-09-12 reports **thirty-one** alt rows, where the reading of 2026-09-09 found twenty-five: six
rows were added to the arm between those dates and two of the six are drawn already. Eleven are
drawn:

- the matrix at every frame and budget of the axis, four rows, the corpus frame at the shipped budget
  on 2026-09-10 and the other three on 2026-09-12;
- the laundering rate at the corpus frame at the shipped budget (2026-09-07) and at the doubled frame
  at the engine's own budget (2026-09-12);
- the picture-cost row at each budget and the canary row, drawn on 2026-09-07 and again on 2026-09-12,
  where the cost rows passed for the first time under the reading `FrameAxis` sorts them into;
- the dialog cell at twenty draws an arm (2026-09-10) and the two token attacks as rates (2026-09-11).

The other twenty are these:

- the rate at the corpus frame at the engine's own budget and at the doubled frame at the shipped
  budget, two rows, both drawn on 2026-09-12 and failed by the void ceiling rather than left undrawn
  ([R-654](654-the-void-ceiling-is-a-share-the-alts-control-arm-is-above.md));
- the payload-size sweep, four rows, one per frame and budget;
- the matrix, the rate and the sweep at the third frame, three rows;
- both budgets' deep rows at a hundred and twenty draws an arm, two rows;
- the `plain` cell's laundering direction at 280 draws an arm at the corpus frame and at 120 at the
  third frame, two rows, and its obeyed direction at 560 draws an arm, one row;
- the mail cell's rate drawn alone at 400 draws an arm, one row;
- the dialog cell's twenty framed draws, the square's four corners, the dialog pair at the falling
  size and the body pair at both legible sizes, four rows;
- the advisory cell at twenty draws an arm behind each of four loads, one row.

**Why it was left.** The sitting that drew the first five had fifty minutes of card time and spent
them on the rows the pick publishes at the corpus frame, which is what makes the two candidates
comparable at all. Its rate of about 12 s a turn against the pick's 2.3, measured over 96 turns at the
shipped budget, was the figure the rest of the list was priced at, and the six frame and budget rows
were priced at about an hour together. They drew on 2026-09-12 at **about 15 s a request**, 306
requests in 4555.90 s with nine cold loads inside it, so those six were about **1:12** and every
estimate resting on 12 s a turn is a fifth low. At 15 s a request the rows left are: each 120-draw
deep row about three hours, 723 requests over three renderings; the `plain` cell's three deep rows
about 2:20, an hour and 4:40, at 561, 241 and 1121 requests; the mail cell's own row 3:20 at 801; each
payload sweep row 25 minutes at 99; and the four corners, the two pairs and the advisory row between
twenty minutes and three quarters of an hour apiece.

**What would close it.** Most of the list is now blocked on a rule rather than on card time, which is
the opposite of the order this entry set. Every row left that draws one cell repeatedly closes through
`assert_drawn`, whose ceiling is one void draw in twenty of a reading's depth, and the alt's control
arm over pixels voids at 7 to 11 in a hundred, so a reading of five passes about half the time and one
of 120 about one time in sixty, and a row is every one of its readings
([R-654](654-the-void-ceiling-is-a-share-the-alts-control-arm-is-above.md), where the depth table and
the two rates are). So the order is: settle that rule first, then the sweep rows, then the deep rows,
which at this candidate's speed are a sitting each. Two rows are drawable before it is settled, the
matrix at the third frame, which closes through `report` rather than the ceiling, and the dialog
cell's twenty framed draws, which draws the framed arm alone, where the alt voided 1 draw in 135. Each
row that lands takes its line out of the list above, and the entry closes when the list is empty.

## Trail

- 2026-09-07: opened by the close of
  [R-586](586-the-cortex-alts-pixel-rows-are-undrawn-now-that-its-artifact-loads.md), whose
  [ADR-0029 corpus-frame addendum](../../adr/ADR-0029-vision-screen-capture.md) publishes the five
  rows that are drawn.
- 2026-09-09: claims held to the tree, and the counts had moved. Collecting the image arm reports
  25 alt rows where the entry says 23, because two rows drawing the `plain` cell deep landed on
  2026-09-08, the day after this was opened, and neither was drawn for the alt. The five drawn rows
  are still the five. The file keeps its name, which spells the old count.
- 2026-09-10: the decision two of these rows waited on is taken. The cost row now sorts a
  candidate's frames into one of two readings and records which one each candidate is in at each
  budget, so an alt frame row has an account to be read under before it is drawn: at the shipped
  budget it is not a frame comparison, and at the engine's own its frames really are three pictures
  ([R-608](608-the-cost-rows-assertions-are-the-picks-saturation-and-the-alt-fails-both.md), the
  [ADR-0029 frame-axis addendum](../../adr/ADR-0029-vision-screen-capture.md)). The rows themselves
  are still undrawn.
- 2026-09-12: **the six frame and budget rows drew, four of them landed, and the count is twenty
  again over a larger arm.** Re-derived first: collecting the arm reports 31 alt rows against the 25
  of 2026-09-09, six rows having been added since, of which the dialog cell in both arms and the two
  token attacks were drawn for the alt on 2026-09-10 and 2026-09-11, so eleven rows are drawn and
  four names join this list. The three matrix rows and the rate at the doubled frame at the engine's
  budget publish their own totals, framing held over every cell both arms drew, and the two cost rows
  reproduce the published token counts. The two rate rows that failed are the void ceiling refusing a
  reading of five draws: the mail control answered nothing in all five at the corpus frame at the
  engine's budget, and the dialog framed arm lost one draw of five at the doubled frame at the shipped
  budget. The sitting is the
  [ADR-0029 frame-and-budget addendum](../../adr/ADR-0029-vision-screen-capture.md), and it opened
  [R-654](654-the-void-ceiling-is-a-share-the-alts-control-arm-is-above.md), which most of this list
  now waits on, and
  [R-655](655-the-canary-rows-ok-cannot-be-told-from-a-void-draw.md).
