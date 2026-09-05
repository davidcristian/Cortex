# Three published pixel matrices and every rate column are re-read from a hand sort

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-09-05 by the close of
[R-543](543-the-description-confound-grows-with-the-image-budget.md), which re-ran one of the
four published pixel matrices under both readings and re-read the other three from what their
addenda say about them.

The readings addendum at ADR-0029 publishes an obeyed count beside the mention count of every
pixel matrix. For the `1600x900` row at the shipped budget the obeyed count is read off the
replies, because that row ran again on 2026-09-05 with the harness printing both readings. For the
other three, `3200x1800` at the shipped budget and both frames at the engine's budget, the obeyed
count is the hand sort their addenda recorded: which fired cells were descriptions was decided
from replies that were stdout of the sitting and are not in the tree, and the addenda summarise
them ("every printed reply for them opens with the model reporting what the dialog says") rather
than print them. A summary that a reply opens with a report does not say how it ends, and the one
recorded `chrome` application opens with a report and ends on the notice. The rate columns are the
same: `chrome` control at 5 of 5 in every column ever published is a mention count, and the
addendum's own sort of one sitting put five of its ten fired arms down as quotes.

**Why it was left.** The close was allowed one live row, and the row that answers the entry's
question is the shipped budget at the corpus frame, where the confound was measured to grow. Three
more matrices are three more cold loads, about fifteen minutes of card time, and the rate rows are
as much again.

**What would close it.** Run `-k "over_pixels and 12B and 3200x1800 and 1024-image-tokens"` and
`-k "over_pixels and 12B and engine-budget"` once each, and the rate rows at each budget, with the
harness as it stands, and replace the hand-sort column in the readings addendum's table with the
count read off the replies. The shipped budget's rate row is already owed a second sitting by
[R-542](542-the-shipped-budgets-rate-row-has-one-sitting.md), and that sitting prints both
readings, so it answers this entry's rate half for that budget.

## Trail

- 2026-09-05: opened by the close of
  [R-543](543-the-description-confound-grows-with-the-image-budget.md), whose readings addendum
  marks which column of its table is read off replies and which off a hand sort.
