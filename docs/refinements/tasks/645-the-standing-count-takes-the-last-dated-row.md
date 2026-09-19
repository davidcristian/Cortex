# The standing count takes the last dated row for the last pass

**Status:** landed 2026-09-15
**Area:** repo-gates
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-checks.md)

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
  [ADR-0002 standing-count addendum](../../adr/ADR-0002-toolchain-checks.md) records the four arms
  the new line was measured over, one of which is the ledger carrying no dated row at all.

- 2026-09-14: re-derived and not fired, and the guess that this entry and
  [R-646](646-the-standing-count-includes-the-pass-day.md) are one defect was tested and is wrong.
  The ledger still carries the two rows of 2026-08-21 and 2026-08-25, both written in the ISO
  format the recipe's pattern matches and both in date order, so the last dated row is the last
  row: `just replay 19269061` prints the pass of 2026-08-25, which is the ledger's last pass.
  Nothing has been appended since, no pass having been run since the one that opened both entries.
  The two entries share the remedy R-646 names, a ledger row carrying the commit the pass was
  recorded at, and they share nothing else. On this one reading R-646's trigger has fired and this
  one's has not, which is only possible because they are two conditions over the same printed line
  rather than one. This entry is about which row the date is read from. R-646 is about how far into
  a day that date reaches once the right row has been read.

- 2026-09-15: **landed**, through the column
  [R-646](646-the-standing-count-includes-the-pass-day.md) named rather than through either remedy
  written above. The ledger grows a "Drawn from" column holding the commit a pass took its sample
  over, and the recipe anchors on the commit nearest HEAD among the rows that carry one, so the
  last pass is whichever row git says is latest. Both failure modes this entry names are gone for a
  row that records a commit: a date cell in another format is never read, and file order decides
  nothing. Two arms in the
  [ADR-0002 drawn-from addendum](../../adr/ADR-0002-toolchain-checks.md) measure it, the rows
  swapped and the older commit moved to the bottom of the table, both still anchoring on the pass
  of 2026-08-25; a third writes the last row's date as `25 August 2026` and still counts 25, where
  the date reading fell through to the row of 2026-08-21 and reported 32. A row with no resolvable
  commit keeps the date fallback and both failure modes with it, which the pass of 2026-08-21 has,
  its tip never having been written down. Opened by this close:
  [R-667](667-a-dateless-row-is-passed-over-by-the-commit-anchor.md).
