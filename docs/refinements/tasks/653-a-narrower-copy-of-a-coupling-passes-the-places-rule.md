# A copy of a coupling over fewer places passes the rule over the places

**Status:** done 2026-09-15
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

The rule that catches a duplicated registry entry is an equality over its places, which is what the
copy it was written for looks like: an entry duplicated into a second part with nothing but its
label changed. A copy that also dropped a place is a different tuple and passes. Measured as the
third row of that rule's mutation table, an entry copied under a new label with one of its two
mentions removed left all 1,798 tests in `scripts/tests` green, and `crosscheck.py` printed
`92 cross-tree constant(s)` over 91 distinct couplings.

The exposure is narrower than the equality's. A copy over fewer places checks a subset of what the
entry it was copied from checks, so it reports a mismatch the original already reports, and no place
goes unchecked. What it costs is what the relabelled copy cost: `shape.entries` counts a collection
the registry does not have, and one mismatch arrives under two labels with nothing saying which
entry is the copy.

**The question underneath.** Whether one entry's places may legitimately contain another's. Two
entries whose sites are identical and whose mentions nest are one coupling twice, but an entry whose
sites are a strict subset of another's declares fewer values and may be a narrower coupling that
stands on its own. If a containment is always a copy, the rule is a pairwise walk reported as two
labels, and the message has to name the narrower one. If only an identical sites tuple makes it a
copy, the rule is a second grouping, by sites alone, which is one line.

## History

- 2026-09-12: opened by the close of
  [R-418](418-a-relabelled-copy-of-a-coupling-is-invisible.md), whose rule is the equality over the
  places and whose mutation table measured this hole as its third row. Not fired: no pair of the 91
  entries has either entry's places contained in the other's, and grouping by sites alone gives 91
  groups of one. Reading the registry pairwise is a different shape of rule from grouping it, 91
  entries being 4,095 pairs.
- 2026-09-15: done, ahead of its trigger and over a registry one entry wider.
  `crosscheck.py --root ..` prints `crosscheck OK: 92 cross-tree constant(s) under .. agree, over
  110 declaring site(s) and 313 mention(s), 27 of them pinned to a count`; grouping those 92 by
  `constant.sites` alone gives 92 groups of one; and over the 4,186 pairs neither entry's places are
  contained in the other's, so both rules were green when added. Recorded in ADR-0042, with the
  boundary these rules stop at filed as
  [R-674](674-a-nested-copy-of-an-ordering-or-a-membership-is-not-read-as-one.md).
