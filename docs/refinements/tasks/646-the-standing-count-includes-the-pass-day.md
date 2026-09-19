# The replay count includes the pass's own day

**Status:** done 2026-09-15
**Area:** repo-checks
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-checks.md)

`just replay` counted commits with `git log --since` set to the ledger's date, which counts from
midnight of that day, so every candidate body committed on the pass's own day was inside the range
whether it came before the pass or after it. Two of the 21 counted on 2026-09-12 are the commits
that added the cadence and recorded the pass of 2026-08-25, so the count of unsampled work was
overstated by the pass's own commits.

The dated reading had counted this way since it was written, so nothing regressed. Correcting it
meant the ledger recording something finer than a date, and that cost falls on the ledger's shape
rather than on the recipe: every past row would have to be read against the new column, for what was
then an error of two in a count of twenty one.

**What closed it.** The ledger grew a "Drawn from" column and the count became the range
`<commit>..HEAD`, which is exactly the work committed after the pass took its sample. The column
holds the sample's tip rather than the commit the pass was recorded at, because a commit's hash does
not exist until the commit is made and no pass can write its own. The same column also closed
[R-645](645-the-standing-count-takes-the-last-dated-row.md), a commit being orderable where a
hand-typed date is only readable.

## History

- 2026-09-12: opened by the close of
  [R-439](439-nothing-counts-the-record-between-passes.md), whose change
  ([ADR-0002](../../adr/ADR-0002-toolchain-checks.md) decision 22) found the two same-day commits
  inside that day's reading.
- 2026-09-14: the trigger fired as written. `just replay 19269061` printed `25 candidate bodies
  since the pass of 2026-08-25, cadence 25: a pass is due`. The count reached the cadence exactly,
  and the two commits of the pass's own day were the whole difference: counting from 2026-08-26
  gives 23, which is under the cadence. So a pass appeared to be due on the two commits that added
  the cadence and recorded the pass of 2026-08-25, which is work that pass had already sampled.
- 2026-09-15: done, and the consequence written in the previous bullet does not survive checking.
  The real ledger counts 26 under the date and 25 under the range. The one body between the two
  readings is the commit that recorded the pass of 2026-08-25, thirteen minutes after the commit
  the sample ran over; the other commit of that day was in the sample's pool, so the overstatement
  is one body and not two, and the result does not move, 25 still reaching the cadence of 25.
  Committed as [ADR-0002](../../adr/ADR-0002-toolchain-checks.md) decision 22, measured over seven
  cases. Opened by this close:
  [R-668](668-a-rewritten-history-unreproduces-a-recorded-draw.md).
