# A nested copy of an ordering or a membership is not read as a copy

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-19
**Trigger:** a second ordering or membership over sites another entry of the same relation already
reads, which is countable by walking `crosscheck.CONSTANTS` pairwise over the entries whose
relation is not `EQUAL` and asking whether either one's sites are a subsequence of the other's.

Opened 2026-09-15 by the close of
[R-653](653-a-narrower-copy-of-a-coupling-passes-the-places-rule.md), which made the registry's key
its sites and added a pairwise walk for the copy that dropped one.

That walk reads two equalities and nothing else. An equality holds between every pair of its sites,
so an equality over fewer of them is implied by the wider entry whatever order either writes its
sites in, which is what makes the containment a copy. The other two relations read their sites
positionally, so set containment says nothing about whether one implies the other: `ORDERED` over
`(C, A)` has its places inside `ORDERED` over `(A, B, C)` and claims the reverse of what that entry
claims, and `MEMBER` over `(A, B)` asks that A be in B where the wider `MEMBER` over `(A, B, C)`
asked that both be in C. A rule refusing either would report as one coupling a pair that was never
compared.

What a nested copy of one of those two really looks like is a **subsequence** with the last site
kept: an ordering over a subsequence of another ordering's sites is implied by it, and a membership
over a subsequence ending at the same collection is implied by it. So the rule is a second shape
beside the one that landed, not a widening of it.

**Why it was left.** Two shapes for three entries. The registry holds 89 equalities, 2 orderings
and 1 membership today, and the two orderings carry two sites each, which is the floor a registry
entry can be written over, so no copy of either could drop a site and still be a registry entry at
all. The rule would therefore be written over a registry that cannot exercise it, which is the
churn the occurrences field was made opt in to avoid.

**What would close it.** One predicate beside `_narrower` in `scripts/tests/test_crosscheck.py`,
reading an ordering's sites as a subsequence of another ordering's and a membership's as a
subsequence sharing its last site, and the same pairwise walk over it. The decision it rests on is
already made and written in the ADR-0029 addendum on the narrower copy: a containment is a copy
exactly where the wider entry's claim implies the narrower one's.

## Trail

- 2026-09-15: opened by the close of
  [R-653](653-a-narrower-copy-of-a-coupling-passes-the-places-rule.md), whose pairwise walk reads
  two equalities and whose third mutation row measured this bound: an ordering planted over three
  bounds and copied over two of them left all 1,835 tests in `scripts/tests` green, and
  `crosscheck.py` printed `94 cross-tree constant(s)` over 93 distinct couplings. Recorded under
  what the ADR-0029 addendum on the narrower copy stops at. Not fired: the registry's three
  non-equalities are `the capture edge ceiling under the brain's image bound`, `the capture
  encoding inside the brain's allow-list` and `the body-client receive limit above the capture
  ceiling`, each over two sites, so none of them can carry a nested copy.
- 2026-09-19: re-derived by the walk the trigger names, and it has not fired. `crosscheck.CONSTANTS`
  holds 92 entries, 89 equalities, 2 orderings and 1 membership, the same three non-equalities over
  two sites each; the one pair of the same relation, the two orderings, shares no site, so neither
  is a subsequence of the other. The floor this entry argues from still holds in code:
  `crosscheck.registry_fault` refuses an entry over fewer than two places and refuses any mention
  on a relation other than `EQUAL`, so an ordering or a membership is two sites at the least. The
  rule that a registry entry must span more than one seam side, which refuses a pair whose places
  all sit in one brain package in one language, narrows a nested copy further without changing
  this entry: its subsequence would have to span two sides as well. `_narrower` is still in
  `scripts/tests/test_crosscheck.py` and still reads two equalities only.
