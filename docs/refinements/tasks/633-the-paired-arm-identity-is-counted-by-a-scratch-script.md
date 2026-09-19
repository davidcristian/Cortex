# The identity between two runs is counted by a scratch script rather than a checked reader

**Status:** done 2026-09-11
**Area:** inference
**Origin:** [ADR-0050](../../adr/ADR-0050-live-probe-records.md)

[ADR-0050](../../adr/ADR-0050-live-probe-records.md) quotes identity counts, two runs of the
envelope harness identical on 4 of 4 cells at one seed and 2 of 4 across a cold start, that were
computed by a scratch script over the per-condition samples. That breaks the rule the entry behind
them stated: a number a document quotes should come out of something `just check` runs, the way
`scripts/envelopefloor.py` verifies the rates and `scripts/switchtail.py` the rendered tails.

**What closed it.** `scripts/envelopepairs.py` and `just envelope-pairs` take two or more samples,
match cells on `question`, `draw` and `seed`, print how many are identical in `output` and `tokens`
for every pair, and refuse a null seed, a repeated cell, unaligned cells, two conditions, or a
matched cell given another instruction or body. The fields are read by `envelopesamples.cells`, so
`Turn` is unchanged.

## History

- 2026-09-11: opened by the close of
  [R-512](512-no-committed-probe-splits-the-reasoning-off-pair.md), which quoted the counts. The
  session that added the settings had spent its time on the live attribution and the cold and warm
  prompt-cache reading, and the comparison is a few lines any reader can re-run over the samples.
- 2026-09-11: done. Checked first: `Turn` read none of the pairing fields and nothing under
  `scripts/` compared two samples. Over runs A, B, C and E the new reader reproduces the three
  counts the paired-conditions session quoted, whose note on them now quotes the reader's output,
  and it refuses run D. The mutation table is in the commit.
