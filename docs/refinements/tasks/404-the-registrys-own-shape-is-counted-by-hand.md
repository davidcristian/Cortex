# The registry's own shape is counted by hand, and goes stale on the next row

**Status:** landed 2026-08-23
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

## Trail

- 2026-08-23: filed by the close of
  [R-397](397-nothing-counts-what-the-registry-does-not-name.md), which declined a coverage reading
  over the tree and noticed the one nobody had asked for was over the registry itself.
- 2026-08-23: landed as `registry.shape`, four numbers over one walk of the tuple `crosscheck.py`
  already walks, printed on the success line beside the entry count it already carried. **This
  file's claims held**, which is rarer in this series than it should be: the scan did print only
  the entry count (`crosscheck.py`, the `crosscheck OK` line), the other numbers were in
  `CONSTANTS`, the counted-mentions tally really was corrected three times on one day (five, nine,
  sixteen, seventeen) and the parts count twice. **What it did not know is that the tally was stale
  while it was being written**: the same sentence said "seventeen registered mentions are counted"
  and "seven the prose sorts added" over a list of eight, the run that bumped the first number
  having left the second alone. A fourth number was therefore printed as well, how many mentions
  pin a count, since that is the tally that keeps rotting and it is the same walk. **Nothing
  asserts any of them**, per this file's own reading: a gate over
  [modules/repo-gates.md](../../modules/repo-gates.md) would tie the gate's prose to the gate's
  data, the exclusion that document has carried since the legibility sort. The suite pins that the
  four numbers count four different things and that the line carries all four, and pins no value
  the registry currently holds. **The prose tallies are gone**, which was the file's other
  option and is taken: that document no longer states how many mentions are counted, how many files
  the registry is written in, or how many parts arrived as splits, and keeps which mentions are
  counted and why. Six planted mutations, three showing the new tests fail and three showing the
  printed numbers move by exactly one in one dimension, tabled in the ADR-0029 registry-shape
  addendum. Two residues filed: the shape counts places and not parts
  ([R-408](408-the-registry-shape-counts-places-not-parts.md)), and the five other gates' success
  lines name no collection at all
  ([R-409](409-a-gates-success-line-names-no-collection.md)).
