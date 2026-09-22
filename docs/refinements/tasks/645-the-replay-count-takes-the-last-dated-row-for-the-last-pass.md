# The replay count takes the last dated row for the last pass

**Status:** done 2026-09-15
**Area:** repo-checks
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-checks.md)

`just replay` prints how many candidate bodies have been committed since the last mutation-replay
pass, read off the ledger in
[docs/runbooks/mutation-replay.md](../../runbooks/mutation-replay.md). The recipe took the last line
whose first cell is an ISO date and counted commits since it, which assumes every pass writes its
date in that format and that rows are appended in date order. Nothing checked either, and the ledger
gains one hand-written row per pass.

The failure was visible rather than silent: the line names the date it read, so a row the pattern
misses prints a date a reader can see is not the last pass, and a table with no dated row says that
in place of a number. A check over one runbook table is more machinery than a two-row table needs,
and the table's other columns are deliberately prose, the first pass's window cell reading "one week
of the record, five tables" and its seed cell "none, chosen by hand".

**What closed it.** The ledger grew a "Drawn from" column holding the commit a pass took its sample
over, and the recipe anchors on the commit nearest HEAD among the rows that have one, so the last
pass is whichever row git says is latest. Both failures are gone for a row that records a commit: a
date cell in another format is never read, and file order decides nothing. A row with no resolvable
commit keeps the date fallback, which the pass of 2026-08-21 does, its tip never having been written
down.

## History

- 2026-09-12: opened by the close of
  [R-439](439-nothing-counts-the-record-between-passes.md), which added the count.
  [ADR-0002](../../adr/ADR-0002-toolchain-checks.md) decision 22 measured the new line over four
  cases, one of which is the ledger with no dated row at all.
- 2026-09-14: checked again, not fired, and the guess that this entry and
  [R-646](646-the-replay-count-includes-the-passs-own-day.md) are one defect was tested and is wrong.
  The ledger still has the two rows of 2026-08-21 and 2026-08-25, both in the ISO format the
  pattern matches and both in date order, so `just replay 19269061` prints the pass of 2026-08-25.
  Nothing has been appended since. The two entries share the column R-646 names and nothing else:
  on this reading R-646's trigger has fired and this one's has not. This entry is about which row
  the date is read from; R-646 is about how far into a day that date reaches once the right row has
  been read.
- 2026-09-15: done, through the column R-646 named rather than through either fix written here. Two
  cases measured at [ADR-0002](../../adr/ADR-0002-toolchain-checks.md) decision 22 show it, the rows
  swapped and the older commit moved to the bottom of the table, both still anchoring on the pass of
  2026-08-25; a third writes the last row's date as `25 August 2026` and still counts 25, where the
  date reading fell through to the row of 2026-08-21 and reported 32. Opened by this close:
  [R-667](667-a-dateless-row-is-passed-over-by-the-commit-anchor.md).
