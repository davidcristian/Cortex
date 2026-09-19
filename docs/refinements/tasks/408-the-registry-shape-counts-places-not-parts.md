# The printed shape counts places and leaves the part count to be counted by hand

**Status:** done 2026-08-24
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

`registry.shape` counts entries, declarations, matches and set counts. It does not count parts,
because `CONSTANTS` is a flat tuple by the time it exists and the parts are gone from it. So the
number removed from [modules/repo-checks.md](../../modules/repo-checks.md), how many data files the
registry is written in, is answered nowhere: a reader counts the imports in `scripts/registry.py`.
That module's own docstring still narrates the count by ordinal, from a sixth part down to a ninth,
which is a running tally in prose of exactly the kind that was removed elsewhere.

The first question is whether the part count is worth having at all. The answer may be no: nothing
in the scan depends on how many files the data sits in, and the suite already globs `*couplings.py`
so a part nobody imported is caught (`test_every_registry_part_on_disk_is_read`).

## History

- 2026-08-23: filed by the close of
  [R-404](404-the-registrys-own-shape-is-counted-by-hand.md), which printed the registry's shape
  over places and left the parts uncounted.
- 2026-08-24: closed, with the counting half declined and the prose half checked. The three claims
  in this file held. `crosscheck.py` imports exactly `CONSTANTS` and `shape` and nothing else in
  `scripts/` imports the registry; `test_every_registry_part_on_disk_is_read` really does catch an
  unimported part, proved by dropping `modelhostcouplings` from the imports and the tuple; and the
  ordinals really are arrival order rather than position. The part count is declined, as a fifth
  integer and as a named mapping from part to its own `Shape`. The argument this file did not have
  is that the same mutation left the check passing on exit 0 printing 48 entries where it prints
  62, so the number that reports a lost part is already on the line, and a part count beside it
  would have moved from nine to eight and changed no result. The mapping's second benefit also
  lost: a fault naming its part saves one grep, every label being distinct, and costs the property
  that the scan never asks which file an entry came from, which would make moving a coupling
  between parts a change to the check's output. What was added instead is a check over the prose.
  The running tally is out of `registry.py`'s docstring, the list of parts stays and is now the
  whole answer to what the registry is written in, and
  `test_registry_names_every_part_in_the_order_it_reads_them` requires that list to be exactly the
  `*couplings.py` files on disk in the order `CONSTANTS` joins them, so a part read but unnamed
  fails where the directory glob cannot see it. The three parts stating their own arrival ordinal
  keep it and now say "to arrive", since the list they sit under is ordered by read order. Five
  planted mutations over the scripts suite. Two residues filed: nothing compares the tuple with the
  parts in the other direction ([R-412](412-nothing-holds-the-registry-to-its-parts.md)), and the
  module contract names the parts twice in prose nothing checks
  ([R-413](413-the-module-contracts-part-list-is-held-by-nobody.md)).
