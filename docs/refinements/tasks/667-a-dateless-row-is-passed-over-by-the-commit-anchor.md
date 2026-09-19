# A dateless row is passed over by the commit anchor

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-checks.md)
**Verified:** 2026-09-19
**Trigger:** the ledger's latest pass has a "Drawn from" cell holding no commit this clone
resolves while an earlier row's does, whether its pass wrote the row without one or a rewrite moved
the commit it recorded and left the earlier one in place, so the standing line counts from a pass
that is not the last one and reports more unsampled work than there is.

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

## Trail

- 2026-09-15: opened by the close of
  [R-645](645-the-standing-count-takes-the-last-dated-row.md) and
  [R-646](646-the-standing-count-includes-the-pass-day.md).
- 2026-09-19: re-derived and left open, the trigger unfired. The ledger in
  `docs/runbooks/mutation-replay.md` still has two rows, and the later one, the pass of
  2026-08-25, records `2712a6aa`, which resolves and is an ancestor of HEAD, so `just replay`
  anchors on the last pass and reports 26 candidate bodies since it, a pass being due. Two things
  were wrong. The trigger named only a pass that omits the commit, and the other road to the same
  case is a rewrite that moves the newest recorded commit and not an older one, which a rewrite of
  work not yet pushed does; the trigger now names both. The runbook, the recipe's comment and the
  origin record all said that a row with no resolvable commit is counted from midnight of its
  date. The recipe only does that when no row's commit resolves, and otherwise passes the row
  over, which is this entry's own case. The runbook and the comment now say what the recipe does,
  and the origin record's 2026-09-19 addendum corrects its own sentence. The fallback
  line also said its row records no commit when the row recorded one that had stopped resolving;
  it now says no row records a commit this clone resolves. The remedy stands: with the anchor
  chosen, compare it against the last row's cell and print a line when they differ.
