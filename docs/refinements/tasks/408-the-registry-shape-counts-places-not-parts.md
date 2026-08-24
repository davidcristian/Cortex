# The printed shape counts places and leaves the part count to be counted by hand

**Status:** landed 2026-08-24
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-23 by the close of
[R-404](404-the-registrys-own-shape-is-counted-by-hand.md), which printed the registry's shape and
removed the hand-counted tallies from the module contract, including the one this file is about.

`registry.shape` counts entries, declaring sites, mentions and pinned counts. It does not count
**parts**, because `CONSTANTS` is a flat tuple by the time it exists and the parts are gone from
it. So the number that the close removed from
[modules/repo-gates.md](../../modules/repo-gates.md), how many data files the registry is written
in, is now answered nowhere: a reader counts the imports in `scripts/registry.py`. That module's
own docstring still narrates the count by ordinal, "the sixth part arrived as a subject", down to a
ninth, which is a running tally in prose of exactly the kind the close removed elsewhere.

**Why it was left.** The close was about the shape a mutation table opens by stating, and that
shape is over places rather than files. Widening it to count parts means either counting the
imports (which `shape` cannot see, being handed a tuple) or having each part announce itself, which
is a change to what a part IS.

**What would close it.** Decide first whether the part count is worth having at all. The honest
alternative is that it is not: nothing in the scan depends on how many files the data sits in, the
suite already globs `*couplings.py` so a part nobody imported is caught
(`test_every_registry_part_on_disk_is_read`), and a narrative of splits is a history rather than a
tally. If it is worth having, the shape is a named mapping from part to its own `Shape` rather than
one more integer, which is also what would let a fault name the part it came from. Check what
`registry.py`'s docstring should then say: a list of parts that names each subject is not stale
prose, but the ordinals counting them are.

## Trail

- 2026-08-23: filed by the close of
  [R-404](404-the-registrys-own-shape-is-counted-by-hand.md), which printed the registry's shape
  over places and left the parts uncounted.
- 2026-08-24: landed, with the counting half declined and the prose half gated. **The three claims
  in this file held.** `crosscheck.py` imports exactly `CONSTANTS` and `shape` and nothing else in
  `scripts/` imports the registry at all; `test_every_registry_part_on_disk_is_read` really does
  catch an unimported part, proved by dropping `modelhostcouplings` from the imports and the
  tuple; and the ordinals really are arrival order rather than position, email having arrived
  sixth and reading seventh. **The part count is declined**, as a fifth integer and as a named
  mapping from part to its own `Shape`. The argument this file did not have is that the same
  mutation left the gate green on exit 0 printing 48 entries where it prints 62, so the number
  that notices a lost part is already on the line and a part count beside it would have moved from
  nine to eight and changed no verdict. The mapping's second benefit was weighed on its own and
  also lost: a fault naming its part saves one grep, every label being distinct, and costs the
  property that the scan never asks which file an entry came from, which would make a coupling
  moving house a change to the gate's output. **What landed instead is the prose being held.** The
  running tally is out of `registry.py`'s docstring, the list of parts stays and is now the whole
  answer to what the registry is written in, and
  `test_registry_names_every_part_in_the_order_it_reads_them` requires that list to be exactly the
  `*couplings.py` files on disk in the order `CONSTANTS` joins them, so a part read but unnamed
  fails where the directory glob cannot see it. The three parts stating their own arrival ordinal
  keep it and now say "to arrive", since the list they sit under is ordered by read order. Five
  planted mutations over the scripts suite, tabled in the ADR-0029 registry-parts addendum. Two
  residues filed: nothing holds the tuple to the parts in the other direction
  ([R-412](412-nothing-holds-the-registry-to-its-parts.md)), and the module contract names the
  parts twice in prose nobody holds
  ([R-413](413-the-module-contracts-part-list-is-held-by-nobody.md)).
