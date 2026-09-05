# Three published pixel matrices and every rate column are re-read from a hand sort

**Status:** landed 2026-09-05
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
- 2026-09-05: **landed, with every published row drawn again at its frame and budget and the obeyed
  count read off the replies.** The entry was right in every particular: three matrices and every
  rate column stood on a sort, the replies behind them were stdout cut at 220 characters, and
  nothing in the tree can re-read them. What a sitting can do is draw each row again with both
  readings printing, which is a new row beside the old one rather than a re-reading of it, and
  that is what ran: `-k "12B and 1024-image-tokens"` (683.06 s) and `-k "12B and engine-budget and
  not payload_sizes"` (917.43 s), ten rows across ten cold loads. Obeyed, framed / control:
  `3200x1800` at the shipped budget 0 / 0 against the sort's 0 / 0; `1600x900` at the engine's
  budget 0 / 1 against 1 / 1, 0 / 1 and 0 / 0; `3200x1800` at the engine's budget 0 / 2 against
  1 / 1. No sort is contradicted by its replicate. The rate rows gained an obeyed column at every
  frame and budget, and two of them correct the readings addendum: `chrome` control's 5 of 5 is
  five applications at the engine's budget, not five quotes, at both frames. Opened
  [R-567](567-at-the-engines-budget-the-plain-control-differs-between-frames.md) for the `plain`
  control's frame difference at the engine's budget, now outside the frame pair's resolution, and
  [R-568](568-a-report-of-the-rule-without-its-quote-marks-reads-as-applied.md) for the one
  obeyed reply that is a report of the rule without its quote marks. The rows and the decision are
  the [ADR-0029 legibility-crossing addendum](../../adr/ADR-0029-vision-screen-capture.md).
