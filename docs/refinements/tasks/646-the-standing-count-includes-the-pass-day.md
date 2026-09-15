# The standing count includes the pass's own day

**Status:** landed 2026-09-15
**Area:** repo-gates
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-gates.md)

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
new column, for what was then an error of two in a count of twenty one. The trail below records
what that error is worth now.

**What would close it.** A ledger row carrying the commit the pass was recorded at, after which the
count is the exact range `<sha>..HEAD` rather than a date and a midnight. The same column would
answer [R-645](645-the-standing-count-takes-the-last-dated-row.md) as a side effect, a commit
being orderable where a hand-typed date is only readable, so the two are worth deciding together.

## Trail

- 2026-09-12: opened by the close of
  [R-439](439-nothing-counts-the-record-between-passes.md), whose
  [ADR-0002 standing-count addendum](../../adr/ADR-0002-toolchain-gates.md) records the two
  same-day commits inside today's reading.

- 2026-09-14: **the trigger fired, in the form it was written in.** `just replay 19269061` now
  prints `25 candidate bodies since the pass of 2026-08-25, cadence 25: a pass is due`. The count
  has reached the cadence exactly, and the two commits of the pass's own day are the whole of the
  difference: counting from 2026-08-26 instead gives 23, which is under the cadence and prints no
  pass due. A pass is therefore being called due on the two commits that landed the cadence and
  recorded the pass of 2026-08-25, which is work that pass had already drawn from. The cost
  argument above no longer holds, because the error is not two at the quiet end of a range but the
  verdict the line exists to give, so this moves to actionable.

- 2026-09-15: **landed, and the consequence written above does not survive the re-derivation.**
  The ledger grows a "Drawn from" column and the count becomes the range `<commit>..HEAD`, which is
  exactly the work that landed after the pass took its sample. The real ledger counts 26 under the
  date and 25 under the range. The one body between the two readings is the commit that recorded
  the pass of 2026-08-25, which landed thirteen minutes after the commit the draw ran over; the
  other commit of that day was in the draw's pool, so the overstatement is one body and not two.
  **The verdict does not move**, 25 reaching the cadence of 25, so the trail above is wrong that a
  pass is being called due on the pass's own commits. The column holds the draw's tip rather than
  the commit the pass was recorded at, because a commit's hash does not exist until the commit is
  made and no pass can write its own; the tip is knowable before the row is written and is what the
  count wants. The seven arms are in the
  [ADR-0002 drawn-from addendum](../../adr/ADR-0002-toolchain-gates.md). Opened by this close:
  [R-668](668-a-rewritten-history-unreproduces-a-recorded-draw.md).
