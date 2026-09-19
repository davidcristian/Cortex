# An alt `app` control cell voids in every draw at the engine's budget, so three rows cannot publish

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-19

Opened 2026-09-19 by the unattended sitting that drew the cortex alt's payload sweeps at the engine's
own budget, published at the
[ADR-0029 eight-row sitting addendum](../../adr/ADR-0029-vision-screen-capture.md). Its log is
`measurements/sitting-2026-09-19/run.log` on the host.

Two cells of the alt's `app` rendering, both control arms at the engine's own budget, returned no
answer in any draw:

- at the corpus frame and the corpus's payload size, 24 px: six draws of six on 2026-09-12 across
  the rate row and the matrix, three replies of 14176 generated tokens on 2026-09-13, each filling
  the server's 16383-token context, and five draws of five tonight in the payload sweep, 70880
  generated tokens together, five times 14176;
- at the third frame, 4800x2700, at 16 px: five draws of five tonight, empty replies after 57475
  generated tokens, 11495 a draw. Whether those filled the context is not printed.

`assert_drawn` fails a reading that loses more than one draw in five, which is the rule every row
of repeated draws is held to, so three rows on
[R-607](607-eighteen-of-the-cortex-alts-pixel-rows-are-undrawn.md)'s list cannot publish: the rate
row at the corpus frame at the engine's own budget and the payload sweeps at the corpus frame and
at the third frame. A redraw is expected to repeat the void: at temperature 0 on a fresh server the
corpus-frame cell has answered nothing in fourteen draws of fourteen across three sittings.

**Why it was left.** Every way out changes what a row measures, so it is a decision rather than a
fix. The server's context could be raised for these rows so the trace can end, which draws the cell
under a condition no other row runs at. A cell that voids in every draw could be read as a finding
of its own, the trace not ending inside the context, and named out of its row's void count, which
lets the row publish every other reading beside it. Or the cell could be left out of these rows for
the alt. Choosing among them is design work, and the publication of the sitting did not include it.

**What would close it.** An ADR-0029 addendum choosing one of those, or another, with its
consequence for the void rule stated; the harness change it needs, with a suite case over the
choice; and the three rows redrawn, which takes their lines out of R-607's list. Tonight's walls
price the two sweeps at 1977 s and 1857 s and the rate row at about a third of a sweep, since it
draws one payload size where a sweep draws three.

## Trail

- 2026-09-19: opened by the unattended sitting, whose sweeps at the corpus frame and at the third
  frame at the engine's own budget each failed their void rule on one of these cells (the
  [ADR-0029 eight-row sitting addendum](../../adr/ADR-0029-vision-screen-capture.md)).
