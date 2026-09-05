# At the engine's budget the plain control differs between the frames in every sitting

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-09-05 by the close of
[R-564](564-three-published-pixel-matrices-are-re-read-from-a-hand-sort.md), which drew the
engine budget's rate rows a second time at both frames with both readings printing.

`plain/output-laundering` control at the engine's own per-image budget is 4 of 5 at the corpus
frame in three sittings (2026-08-04, 2026-08-30, 2026-09-05) and 1 of 5 and 0 of 5 at the doubled
frame in two (2026-08-30, 2026-09-05), obeyed on every printed reply where replies were printed.
The frame-pair addendum read the first pair of those, 4 of 5 against 1 of 5, as inside the 2 of 5
one cell had moved between two sittings at one frame, and concluded that no frame effect larger
than the arm's instability exists. With a second sitting at each frame the gap on this cell is
wider than that resolution, and it has the same sign in every sitting.

At this budget the two frames cost the same 266 tokens, which the cost row measured again the
same night, so the doubled frame is not more picture reaching the model. It is the same token
count over a picture the encoder resampled from twice the pixels, whose glyph edges are not the
corpus frame's. Two deliveries of one picture at one token count are still two encodings.

**Why it was left.** It is on the budget no deployment runs. At the shipped budget the same cell is
0 of 5 at both frames in every sitting, three at the corpus frame and two at the large one, so
nothing the ADR decides about the shipped stack rests on it; what rests on it is the frame-pair
addendum's sentence that the corpus's frame is a free choice at both budgets, which for this one
cell at the engine's budget it may not be.

**What would close it.** Run `-k "laundering_rate and 12B and engine-budget"` once more, which is
two cold loads, and read `plain` control. If the corpus frame draws 4 of 5 again and the doubled
frame draws 0 or 1 of 5 again, the frame-pair addendum's ceiling holds at the shipped budget only,
and its sentence about both budgets is narrowed. If either frame draws the other's number, the
five sittings were the instability landing the same way four times and the ceiling stands. Either
way the frame pair's own resolution, five runs per cell, is the instrument, and a third sitting at
each frame is what makes it decisive.

## Trail

- 2026-09-05: opened by the close of
  [R-564](564-three-published-pixel-matrices-are-re-read-from-a-hand-sort.md), whose engine-budget
  rate rows drew the cell at 4 of 5 and 0 of 5 for the third and second time.
