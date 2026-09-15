# A copy of a coupling over fewer places passes the rule over the places

**Status:** landed 2026-09-15
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-09-12 by the close of
[R-418](418-a-relabelled-copy-of-a-coupling-is-invisible.md), which grouped the registry by each
entry's sites and mentions so that two labels over one tuple of places fail.

That rule is an equality over the places, which is what the copy it was written for looks like: an
entry duplicated into a second part with nothing but its label changed. A copy that also dropped a
place is a different tuple and passes. Measured as the third row of that close's mutation table, an
entry copied under a new label with one of its two mentions removed left all 1,798 tests in
`scripts/tests` green, and `crosscheck.py` printed `92 cross-tree constant(s)` over 91 distinct
couplings, the same false count the label rule and the places rule were both written to remove.

The exposure is narrower than the equality's was, and the bound is worth stating. A copy over
fewer places checks a subset of what the entry it was copied from checks, so it reports a drift the
original already reports rather than a drift nobody sees, and no place goes unchecked. What it
costs is the same two things the relabelled copy cost: `shape.entries` counts a collection the
registry does not have, and one drift arrives under two labels with nothing saying which entry is
the copy.

**Why it was left.** The close it came out of was a rule with a mutation table, and reading the
registry pairwise is a different shape of rule from grouping it: 91 entries are 4,095 pairs today,
and a containment walk has to say which of the two entries it thinks is the copy, where a group
says only that the group exists. There is also a real question underneath it, the same one the
equality had to answer: whether one entry's places may ever legitimately contain another's. Two
entries whose sites are identical and whose mentions nest are one coupling twice, but an entry
whose sites are a strict subset of another's declares fewer values and may be a narrower coupling
that stands on its own, which grouping never had to decide.

**What would close it.** Decide that question first, since it picks the rule. If a containment is
always a copy, the rule is a pairwise walk reported as two labels and the sentence has to name the
narrower one. If only an identical sites tuple makes it a copy, the rule is a second grouping, by
sites alone, which is one line beside the one that landed and which is green today: grouping the
registry by `constant.sites` gives 91 groups of one, so no two entries even name the same
declaring sites.

## Trail

- 2026-09-12: opened by the close of
  [R-418](418-a-relabelled-copy-of-a-coupling-is-invisible.md), whose rule is an equality over the
  places and whose mutation table measured this hole as its third row. Recorded under what the
  ADR-0029 relabelled-copy addendum stops at. Not fired: no pair of the 91 entries has either
  entry's places contained in the other's, and grouping by sites alone gives 91 groups of one.
- 2026-09-15: landed, ahead of its trigger and over a registry one entry wider. `crosscheck.py
  --root ..` prints `crosscheck OK: 92 cross-tree constant(s) under .. agree, over 110 declaring
  site(s) and 313 mention(s), 27 of them pinned to a count`; grouping those 92 by `constant.sites`
  alone gives 92 groups of one; and over the 4,186 pairs neither entry's places are contained in
  the other's, so both rules landed green. Recorded in the ADR-0029 addendum on the narrower copy,
  which carries the mutation table and the boundary these rules stop at, filed as
  [R-674](674-a-nested-copy-of-an-ordering-or-a-membership-is-not-read-as-one.md).
