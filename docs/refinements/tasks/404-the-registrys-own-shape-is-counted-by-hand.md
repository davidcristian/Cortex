# The registry's own shape is counted by hand, and goes stale on the next row

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-23 by the close of
[R-397](397-nothing-counts-what-the-registry-does-not-name.md), which declined a coverage reading
over the tree and noticed that the one reading nobody had asked for is over the registry itself.

Every mutation table in this series opens by stating the registry's shape, entries over sites and
mentions, so that its counts name the collection they are over. Each of those numbers was counted
by hand, and each was stale the moment the next row landed:
[modules/repo-gates.md](../../modules/repo-gates.md)'s tally of which mentions carry an
`occurrences` count has now been corrected three times in one day, and its account of how many
files the registry is written in twice.

`crosscheck.py` already prints one of the three on success ("N cross-tree constant(s) ... agree").
It holds the other two in the same tuple it is already walking.

**Why it was left.** The close it came out of decided that a reading over the *tree* is not worth
building, and adding a reading over the *registry* inside that close would have buried a small
feature under a decline.

**What would close it.** Print sites and mentions beside the entry count, and decide one thing
while doing it: whether anything may **assert** those numbers. It may not be a gate over the
documents that quote them. Holding [modules/repo-gates.md](../../modules/repo-gates.md) to the
registry's shape would tie the gate's own prose to the gate's own data, which is the exclusion the
legibility sort already wrote down and which a document describing the registry has always had.
So the deliverable is a line of output an addendum's author reads, not a check, and the honest
version of "the tally goes stale" may be to stop writing the tally in prose at all.
