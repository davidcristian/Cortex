# The printed shape counts places and leaves the part count to be counted by hand

**Status:** open, actionable
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
