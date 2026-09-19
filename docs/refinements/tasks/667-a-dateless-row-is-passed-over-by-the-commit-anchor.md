# A dateless row is passed over by the commit anchor

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-checks.md)
**Verified:** 2026-09-15
**Trigger:** a pass writes a ledger row whose "Drawn from" cell holds no commit this clone
resolves while an earlier row's does, so the standing line counts from a pass that is not the last
one and reports more unsampled work than there is.

Opened 2026-09-15 by the close of
[R-645](645-the-standing-count-takes-the-last-dated-row.md) and
[R-646](646-the-standing-count-includes-the-pass-day.md), which gave `just replay` a standing count
anchored on the commit nearest HEAD among the ledger rows that carry one. That ordering is what
closed R-645: the anchor no longer depends on which row is last in the file. It also means a row
carrying no commit takes no part in the ordering at all, where the reading it replaced always took
the last dated row. So the two readings disagree in one case, a later row without a commit sitting
above an earlier row with one, and the commit reading is the wrong one there.

**Why it was left this way.** The failure is visible rather than silent, which is the argument
R-645 was left on. The line names the row it counted from and the commit it counted from, so a
reader looking at the number sees the pass of an older date beside it. The case also needs a pass
to omit the column the runbook tells it to fill, in a table gaining one hand-written row per pass,
and the runbook's instruction is one `git rev-parse HEAD` before the draw.

**What would close it.** Comparing the anchor row against the ledger's last row and reporting when
they differ, which is the first remedy R-645 named and which is still a few lines where the parse
already happens. The comparison is cheaper now than it was there: with the commit column, the two
sides are a commit and a row rather than two dates, so "differ" is an equality rather than a
judgement about date formats.
