# A dateless row is passed over by the commit anchor

**Status:** open, waiting for its trigger
**Area:** repo-checks
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-checks.md)
**Verified:** 2026-09-19
**Trigger:** the ledger's latest pass has a "Drawn from" cell with no commit this clone resolves
while an earlier row's does, whether its pass wrote the row without one or a rewrite moved the
commit it recorded and left the earlier one in place, so the replay line counts from a pass that is
not the last one and reports more unsampled work than there is.

`just replay` anchors its count on the commit nearest HEAD among the ledger rows that have one. That
ordering is what closed [R-645](645-the-replay-count-takes-the-last-dated-row-for-the-last-pass.md): the anchor no
longer depends on which row is last in the file. It also means a row with no commit takes no part in
the ordering, where the reading it replaced always took the last dated row. So the two disagree in
one case, a later row without a commit above an earlier row with one, and the commit reading
is the wrong one there.

The failure is visible rather than silent, which is the argument R-645 was left on: the line names
the row and the commit it counted from, so a reader sees the pass of an older date beside the
number. The case also needs a pass to omit the column the runbook tells it to fill, in a table that
gains one hand-written row per pass, and the runbook's instruction is one `git rev-parse HEAD`
before the draw.

**What would close it.** Comparing the anchor row against the ledger's last row and reporting when
they differ, which is the first fix R-645 named and is still a few lines where the parse already
happens. It is cheaper now: with the commit column, the two sides are a commit and a row rather than
two dates, so "differ" is an equality rather than a judgement about date formats.

## History

- 2026-09-15: opened by the close of
  [R-645](645-the-replay-count-takes-the-last-dated-row-for-the-last-pass.md) and
  [R-646](646-the-replay-count-includes-the-passs-own-day.md).
- 2026-09-19: checked again and left open, the trigger unfired. The ledger in
  `docs/runbooks/mutation-replay.md` still has two rows, and the later one, the pass of 2026-08-25,
  records `2712a6aa`, which resolves and is an ancestor of HEAD, so `just replay` anchors on the
  last pass and reports 26 candidate bodies since it. Two things were wrong. The trigger named only
  a pass that omits the commit, and the other route to the same case is a rewrite that moves the
  newest recorded commit and not an older one, which a rewrite of work not yet pushed does; the
  trigger now names both. The runbook, the recipe's comment and the origin record all said that a
  row with no resolvable commit is counted from midnight of its date; the recipe only does that when
  no row's commit resolves, and otherwise passes the row over, which is this entry's own case. All
  three now say what the recipe does, and the fallback sentence now says that no row records a
  commit this clone resolves rather than that the row records none.
