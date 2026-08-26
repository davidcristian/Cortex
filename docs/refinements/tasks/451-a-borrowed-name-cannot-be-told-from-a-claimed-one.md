# A name a roster borrows cannot be told from a name it claims

**Status:** open, fix when it bites
**Trigger:** a sentence in the borrowing half makes one of the borrowed names its subject rather
than its owner, which reads to a human as a claim about that module and to the gate as a
reference, so the sentence is wrong and green.
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-26 by the close of
[R-448](448-the-module-listing-is-held-whole-and-not-in-halves.md), which split one paragraph of
[modules/repo-gates.md](../../modules/repo-gates.md) into two rosters and had to let one of them
carry names belonging to the other.

The second half of that paragraph says whose reader each library is, and it says it with the CLI
modules' names: `composemounts.py` is `bindcheck.py`'s mount reader, `logsamples.py` and
`logcalls.py` are the two sides `samplecheck.py` holds together. Seven such names stand there
today. A roster may therefore declare the sibling set whose names its passage is allowed to
carry, and every name in that set is accepted wherever it falls in the passage.

What that cannot see is the difference between `composemounts.py` is `bindcheck.py`'s mount reader
and `bindcheck.py` is `composemounts.py`'s mount reader. Both sentences name the same two modules
and only one of them is true. The gate reads the second as a library described beside a reference
and passes it.

The exposure is bounded and the bound is worth stating: a CLI module written into the second half
as a claim is still a member of the first half, which reports it as a member nobody named. So the
failure that survives is a sentence that reads wrongly about a module the other half already
accounts for, never a set that has silently drifted.

**Why it was left.** Telling a reference from a claim means reading the grammar of the sentence,
which is a different kind of reader from anything in this tree: every reader here answers what a
document names, and none answers what it says. A possessive marker after a code span is the
cheapest approximation and it is wrong in both directions, since the paragraph also writes "the
two sides `samplecheck.py` holds together" with no possessive at all, and a library's own entry
could take one.

**What would close it.** Either a rule narrow enough to be honest, for instance that a borrowed
name is accepted only where it is not the subject of the clause it opens, with the paragraph
rewritten to a shape that rule can read; or a written argument that the bound above is the right
place to stop, since the half that matters is already held twice and the residue is prose quality
rather than drift.

## Trail

- 2026-08-26: opened by the close of
  [R-448](448-the-module-listing-is-held-whole-and-not-in-halves.md), whose borrowed-name
  allowance is what makes the hole. Recorded under what the ADR-0029 addendum on holding that
  listing in halves defers.
