# The standing count includes the pass's own day

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-gates.md)
**Verified:** 2026-09-12
**Trigger:** a standing count reaches the cadence and the bodies from the pass's own day are the
difference, so a pass is called due on work the last pass had already drawn from.

Opened 2026-09-12 by the close of
[R-439](439-nothing-counts-the-record-between-passes.md), which gave `just replay` a standing count
off the ledger in [docs/runbooks/mutation-replay.md](../../runbooks/mutation-replay.md). The count
runs `git log` with `--since` set to the ledger's date, and that counts from midnight of the day,
so every candidate body that landed on the pass's own day is inside the range whether it landed
before the pass or after it. Two of the 21 counted on 2026-09-12 are the commits that landed the
cadence and recorded the pass of 2026-08-25, so the count of unsampled work is overstated by the
pass's own commits.

**Why it was left this way.** The dated arm has counted this way since it was written and the
standing count inherits it, so nothing regressed and no reading taken before today was any
narrower. Correcting it means the ledger recording something finer than a date, and the cost lands
on the ledger's shape rather than on the recipe: every past row would have to be read against the
new column, for an error of two in twenty one.

**What would close it.** A ledger row carrying the commit the pass was recorded at, after which the
count is the exact range `<sha>..HEAD` rather than a date and a midnight. The same column would
answer [R-645](645-the-standing-count-takes-the-last-dated-row.md) as a side effect, a commit
being orderable where a hand-typed date is only readable, so the two are worth deciding together.

## Trail

- 2026-09-12: opened by the close of
  [R-439](439-nothing-counts-the-record-between-passes.md), whose
  [ADR-0002 standing-count addendum](../../adr/ADR-0002-toolchain-gates.md) records the two
  same-day commits inside today's reading.
