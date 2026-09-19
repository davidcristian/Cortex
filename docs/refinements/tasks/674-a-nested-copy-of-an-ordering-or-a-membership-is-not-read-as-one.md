# A nested copy of an ordering or a membership is not read as a copy

**Status:** open, waiting for its trigger
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)
**Verified:** 2026-09-19
**Trigger:** a second ordering or membership over sites another entry of the same relation already
reads, which is countable by walking `crosscheck.CONSTANTS` pairwise over the entries whose relation
is not `EQUAL` and asking whether either one's sites are a subsequence of the other's.

The pairwise walk that catches a copied registry entry reads two equalities and nothing else. An
equality holds between every pair of its sites, so an equality over fewer of them is implied by the
wider entry whatever order either writes its sites in, which is what makes the containment a copy.
The other two relations read their sites positionally, so set containment says nothing about whether
one implies the other: `ORDERED` over `(C, A)` has its places inside `ORDERED` over `(A, B, C)` and
claims the reverse of what that entry claims, and `MEMBER` over `(A, B)` asks that A be in B where
the wider `MEMBER` over `(A, B, C)` asked that both be in C. A rule refusing either would report as
one coupling a pair that was never compared.

A nested copy of one of those two is a **subsequence** with the last site kept: an ordering over a
subsequence of another ordering's sites is implied by it, and a membership over a subsequence ending
at the same collection is implied by it. So the rule is a second shape beside the one that exists,
not a widening of it.

**Why it was left.** Two shapes for three entries. The registry has 89 equalities, 2 orderings and 1
membership today, and the two orderings have two sites each, which is the fewest a registry entry
can be written over, so no copy of either could drop a site and still be a registry entry.

**What would close it.** One predicate beside `_narrower` in `scripts/tests/test_crosscheck.py`,
reading an ordering's sites as a subsequence of another ordering's and a membership's as a
subsequence sharing its last site, and the same pairwise walk over it. The decision it rests on is
already written in ADR-0042: a containment is a copy exactly where the wider entry's claim implies
the narrower one's.

## History

- 2026-09-15: opened by the close of
  [R-653](653-a-narrower-copy-of-a-coupling-passes-the-places-rule.md), whose pairwise walk reads
  two equalities and whose third mutation row measured this bound: an ordering planted over three
  bounds and copied over two of them left all 1,835 tests in `scripts/tests` green, and
  `crosscheck.py` printed `94 cross-tree constant(s)` over 93 distinct couplings. Not fired: the
  registry's three non-equalities are `the capture edge ceiling under the brain's image bound`, `the
  capture encoding inside the brain's allow-list` and `the body-client receive limit above the
  capture ceiling`, each over two sites.
- 2026-09-19: checked again by the walk the trigger names, and it has not fired.
  `crosscheck.CONSTANTS` has 92 entries, 89 equalities, 2 orderings and 1 membership, the same three
  non-equalities over two sites each; the one pair of the same relation, the two orderings, shares
  no site, so neither is a subsequence of the other. The minimum this entry argues from still holds
  in code: `crosscheck.registry_fault` refuses an entry over fewer than two places and refuses any
  mention on a relation other than `EQUAL`. The rule that a registry entry must span more than one
  side of the body/brain boundary, which refuses a pair whose places all sit in one brain package in
  one language, narrows a nested copy further without changing this entry: its subsequence would
  have to span two sides as well. `_narrower` is still in `scripts/tests/test_crosscheck.py` and
  still reads two equalities only.
