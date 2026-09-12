# The standing count takes the last dated row for the last pass

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-gates.md)
**Verified:** 2026-09-12
**Trigger:** the date the standing line prints is not the date of the ledger's last pass, which
is what a row dated in another format or appended out of order produces.

Opened 2026-09-12 by the close of
[R-439](439-nothing-counts-the-record-between-passes.md), which gave `just replay` a standing count
read off the ledger in [docs/runbooks/mutation-replay.md](../../runbooks/mutation-replay.md). The
recipe takes the last line whose first cell is an ISO date and counts candidate bodies since it.
That depends on two properties of the table: every pass writes its date in that format, and rows
are appended in date order. Nothing holds the table to either, and the ledger gains one
hand-written row per pass.

**Why it was left this way.** The failure is visible rather than silent. The line names the date it
read, so a row the pattern misses prints a date a reader can see is not the last pass, and a table
with no dated row at all says that in place of a number. A scan over one runbook table is more
machinery than a two row table carries, and the table's other columns are deliberately prose: the
first pass's window cell reads "one week of the record, five tables" and its seed cell reads "none,
chosen by hand".

**What would close it.** Either the recipe comparing the last dated row against the last row of the
table and reporting when they differ, which is a few lines where the parse already happens, or a
scan holding the first column to an ISO date, which is a new gate over one document and is the
shape [R-439](439-nothing-counts-the-record-between-passes.md) declined for failing a commit on a
condition no commit caused.

## Trail

- 2026-09-12: opened by the close of
  [R-439](439-nothing-counts-the-record-between-passes.md), whose
  [ADR-0002 standing-count addendum](../../adr/ADR-0002-toolchain-gates.md) records the four arms
  the new line was measured over, one of which is the ledger carrying no dated row at all.
