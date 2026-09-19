# A coupling copied into a second part and relabelled is two entries checking one thing

**Status:** done 2026-09-12
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

Requiring every label in `CONSTANTS` to be distinct catches the copy this design invites: the scan
never asks which file an entry came from, so a coupling moves between parts freely, and a move done
as a copy without a delete leaves the same entry in two parts under the same label. It does not
catch the copy that was also renamed. Two entries with different labels over an identical tuple of
declarations and matches pass the equality, pass the label check, and are counted twice by
`shape.entries`, which is the same wrong count of the collection's size that the label rule was
added to catch. A change at those places is then reported twice, once per label, and a reader
cannot tell one coupling described twice from two couplings that genuinely overlap.

## History

- 2026-08-24: opened by the close of
  [R-412](412-nothing-holds-the-registry-to-its-parts.md), which enforced the registry's entry
  count by requiring every label to be distinct. Measured on the day that was added, no two entries
  shared a places tuple, so this was a hole rather than a defect.
- 2026-09-08: trigger checked and not fired. `crosscheck.py --root ..` prints
  `crosscheck OK: 89 cross-tree constant(s) under .. agree, over 105 declaring site(s) and 291
  mention(s), 25 of them pinned to a count`, and grouping those 89 entries by
  `(constant.sites, constant.mentions)` gives 89 groups of one. The stronger reading holds too:
  grouping by `constant.sites` alone also gives 89 groups. The registry had 67 entries when this
  was opened and has 89 now, so 22 entries have been written since without one of them repeating a
  places tuple.
- 2026-09-08: the account of the existing check is still accurate.
  `test_the_registry_holds_each_coupling_once` counts labels and nothing else, so a relabelled copy
  passes it, and `registry.shape` counts entries with no regard for what any entry names. The entry
  stays open with its open question unanswered, since deciding whether two entries may legitimately
  name the same places cannot be settled by counting.
- 2026-09-12: closed, and the question was settled by reading `Relation` rather than by counting.
  `test_no_two_couplings_are_written_over_one_set_of_places` in
  `scripts/tests/test_crosscheck.py` groups `CONSTANTS` by each entry's declarations and matches
  and fails on a group larger than one, naming every label in the group. Whether two entries may
  ever legitimately name the same places is answered no, and the argument for yes dissolved when it
  was read: that argument was `Relation`, one pair of declarations tied as an equality and again as
  an ordering against a third. A third declaration is a third place, so the ordering's tuple is not
  the equality's and the pair was never a collision. The relation is therefore left out of the
  grouping, which is the narrower rule: including it would pass a copy that flipped `EQUAL` to
  `ORDERED`, and over identical declarations that copy is either redundant or contradictory. The
  registry has 91 entries over 109 declarations and 300 matches, 27 of them with a count, and
  grouping by places still gives 91 groups of one, so the rule passed on the day it was added and
  ahead of its trigger. Recorded in ADR-0042, with the boundary the rule stops at: a copy whose
  places are a strict subset of another entry's passes the whole suite, which is
  [R-653](653-a-narrower-copy-of-a-coupling-passes-the-places-rule.md).
