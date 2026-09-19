# The registry's own shape is counted by hand and goes stale on the next row

**Status:** done 2026-08-23
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

Every mutation table in this series opens by stating the registry's shape, entries over
declarations and matches, so its counts name the collection they are over. Each of those numbers
was counted by hand, and each was stale as soon as the next row was added:
[modules/repo-checks.md](../../modules/repo-checks.md)'s tally of which matches have an
`occurrences` count was corrected three times in one day, and its account of how many files the
registry is written in twice.

`crosscheck.py` already prints one of the three on success ("N cross-tree constant(s) ... agree").
The other two are in the same tuple it is already walking.

Printing them raises one decision: whether anything may assert those numbers. It may not be a check
over the documents that quote them. Comparing [modules/repo-checks.md](../../modules/repo-checks.md)
with the registry's shape would tie the check's own prose to the check's own data, which is the
exclusion that document has always had. So the deliverable is a line of output an author reads, not
a check, and the accurate answer to "the tally goes stale" may be to stop writing the tally in
prose at all.

## History

- 2026-08-23: filed by the close of
  [R-397](397-nothing-counts-what-the-registry-does-not-name.md), which declined a coverage reading
  over the tree and noticed the one nobody had asked for was over the registry itself.
- 2026-08-23: closed as `registry.shape`, four numbers over one walk of the tuple `crosscheck.py`
  already walks, printed on the success line beside the entry count. This file's claims held, which
  is rarer in this series than it should be: the scan did print only the entry count, the other
  numbers were in `CONSTANTS`, the counted-matches tally really was corrected three times on one
  day (five, nine, sixteen, seventeen) and the parts count twice. What it did not know is that the
  tally was stale while it was being written: the same sentence said "seventeen registered mentions
  are counted" and "seven the prose sorts added" over a list of eight, the run that raised the
  first number having left the second alone. A fourth number was therefore printed as well, how
  many matches have a count, since that is the tally that keeps going stale and it is the same
  walk. Nothing asserts any of them, per this file's own reading. The suite checks that the four
  numbers count four different things and that the line contains all four, and checks no value the
  registry currently holds. The prose tallies are gone, which was this file's other option: that
  document no longer states how many matches are counted, how many files the registry is written
  in, or how many parts arrived as splits, and keeps which matches are counted and why. Six planted
  mutations, three showing the new tests fail and three showing the printed numbers move by exactly
  one in one dimension. Two residues filed: the shape counts places and not parts
  ([R-408](408-the-registry-shape-counts-places-not-parts.md)), and the five other checks' success
  lines name no collection at all
  ([R-409](409-a-gates-success-line-names-no-collection.md)).
