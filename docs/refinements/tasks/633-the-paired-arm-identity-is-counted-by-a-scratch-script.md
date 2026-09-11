# The paired-arm identity is counted by a scratch script rather than a gated reader

**Status:** landed 2026-09-11
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-09-11 by the close of
[R-512](512-no-committed-probe-splits-the-reasoning-off-pair.md). The ADR-0005 paired-arms addendum
quotes identity counts, two runs of the envelope harness identical on 4 of 4 cells at one seed and
2 of 4 across a cold start, that were computed by a scratch script over the per-arm samples. That
is against the rule the closed entry itself stated: a number a document quotes should come out of
something a gate runs, the way `scripts/envelopefloor.py` holds the rates and `scripts/switchtail.py`
the rendered tails.

**What would close it.** A reader beside `envelopefloor.py`, say `scripts/envelopepairs.py`, taking
two or more sample files, matching turns on `question`, `draw` and `seed`, and reporting how many
cells are identical in `output` and `tokens`, refusing a pair whose seeds are null or whose cells
do not line up. `envelopesamples.Turn` reads four fields of a turn and none of these, so the reader
widens that tuple or reads the file on its own, and the module's suite gains the cases with a
mutation table naming the suite the counts are over.

**Why it was left.** The sitting that landed the knobs spent its runway on the live attribution,
the cold and warm prompt-cache reading, and the comparison is a few lines any reader can re-run
over the samples. The cost of not having it is that the counts in the addendum are a hand run
labelled as one.

## Trail

- 2026-09-11: opened by the close of
  [R-512](512-no-committed-probe-splits-the-reasoning-off-pair.md), whose paired-arms addendum
  quotes the counts.
- 2026-09-11: landed. Re-derived first: `Turn` read none of the pairing fields and nothing under
  `scripts/` compared two samples. `scripts/envelopepairs.py` and `just envelope-pairs` take two or
  more samples, match cells on `question`, `draw` and `seed`, print how many are identical in
  `output` and `tokens` for every pair, and refuse a null seed, a repeated cell, unaligned cells,
  two arms, or a matched cell given another instruction or body. The fields are read by
  `envelopesamples.cells`, leaving `Turn` as the floor reads it. Over runs A, B, C and E it
  reproduces the three counts the paired-arms addendum quotes, whose note on them now quotes the
  reader's output, and it refuses run D. The pairs-reader addendum at the origin has the mutation
  table.
