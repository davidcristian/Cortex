# The fence obligation stops at the suites

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-gates.md)
**Verified:** 2026-09-12
**Trigger:** a module under `scripts/tests/` that answers for itself whether a line is a fence,
rather than writing a fenced document as the data its reader is asked about.

Opened 2026-09-12 by the close of
[R-445](445-three-gates-each-spell-the-markdown-fence-for-themselves.md), which made
`markdownfences.py` the one module under `scripts/` allowed to spell a fence marker and held the
rest to it.

The set that obligation is compared over is `scripts/*.py`, and the suites beside those modules are
outside it. They have to be: seven of them write a fence marker today, and every one of those
markers is a fixture rather than an answer. `test_logsamples.py` and `test_samplecheck.py` write a
fenced sample in the shapes the runbooks carry, `test_commitlint.py` parametrizes the four
spellings a message may open a paste with, `test_headingshapes.py` and `test_backloganchors.py`
each write a block holding a shell comment, `test_rosternames.py` writes a fenced command into the
page a roster is read out of, and `test_markdownfences.py` writes the markers the shared answer is
asked about. A suite that grew
a reader of its own would be indistinguishable from those by the set the obligation compares.

Nothing is wrong in the tree today, and the bite is smaller than a gate's: a fence reader inside a
suite would decide what that suite's own fixtures mean, where a second reader in a module decides
what a gate reports about the repo.

[R-610](610-the-descent-obligation-stops-at-the-suites.md) is the sibling entry, the same boundary
on the descent obligation for a different reason: there one suite has a reason to descend
independently, here every suite has a reason to spell a marker.

**What would close it.** Either a rule by shape rather than by file, since a marker that reaches a
`re.compile`, a `startswith` or an `in` test is a reader and a marker inside a document string is
data, which is the same move that widened the two obligations over calls; or a written argument at
the origin that the suites are outside this obligation on purpose, so the next reader of it knows
the boundary is a decision.

## Trail

- 2026-09-12: opened by the close of
  [R-445](445-three-gates-each-spell-the-markdown-fence-for-themselves.md), whose
  [ADR-0026 one-home addendum](../../adr/ADR-0026-prose-style-gates.md) records the set the
  obligation is compared over and why the suites are not in it.
