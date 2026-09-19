# The fence obligation stops at the suites

**Status:** declined 2026-09-15
**Area:** repo-gates
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-checks.md)

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
  [ADR-0026 one-home addendum](../../adr/ADR-0026-prose-style-checks.md) records the set the
  obligation is compared over and why the suites are not in it.
- 2026-09-14: still not fired, and the same correction the sibling entry now carries applies
  here. Seven suites write a fence marker, the seven this entry names, and all 48 of their markers
  are fixtures: `test_rosternames.py`, `test_commitlint.py`, `test_logsamples.py`,
  `test_samplecheck.py`, `test_backloganchors.py`, `test_markdownfences.py` and
  `test_headingshapes.py`. None of them tests a line for a marker. What the entry does not say is
  that the boundary it describes is not the family's. `test_gitenv.py` compares its obligation
  over `[*GATES.glob("*.py"), *GATES.glob("tests/*.py")]`, so of the three obligations here one
  covers the suites and two do not.

  This is the sibling of [R-610](610-the-descent-obligation-stops-at-the-suites.md) and it is not
  the same defect, which is worth writing down because the two names invite the guess. They share
  a cause, the comparison set spelled per suite rather than once, and nothing else: widening this
  one needs a rule that tells a marker reaching a `re.compile`, a `startswith` or an `in` test
  from a marker inside a document string, and widening that one needs a second reader in
  `treewalk.py` for the suite with a reason to descend independently. One fix closes neither the
  other. The written-argument branch is the half they really share, and after the reading above it
  can no longer be written as "the suites are outside these obligations", only as a decision per
  obligation with the third named.
- 2026-09-15: declined, alongside [R-610](610-the-descent-obligation-stops-at-the-suites.md) and
  for its own reason. The count was re-derived: seven suites spell a fence marker, 65 literals on
  42 lines, and every one of the 65 was classified by the syntax around it. None reaches a
  `re.compile`, a `startswith`, a `match` or a comparison. They are fixture documents,
  parametrized spellings, and the markers the shared answer is asked about.

  The rule by shape is refused, and on a ground this entry did not state. The obligation is over
  literals, so a module importing `MARKERS` and testing a line against it is reported by nothing
  today, in a module as much as in a suite. A shape rule would therefore enumerate the positions
  that count as reading while leaving that hole open, which buys a weaker rule than the one it
  widens. What the obligation holds is that the marker is spelled once, and a suite writing a
  fixture is not a second spelling of it. The written argument is the
  [ADR-0026 addendum on where each obligation stops](../../adr/ADR-0026-prose-style-checks.md),
  which records the boundary per obligation and names the git-environment one that covers the
  suites; `scripts/tests/test_markdownfences.py`'s docstring now carries the pointer.

  What would reopen this is a suite found testing a line against a marker rather than writing one
  into a document, which is the first case the widened obligation would have caught. The reading
  that refused the shape rule also opened
  [R-669](669-the-fence-obligation-is-over-literals-only.md), the hole it names being a module's
  as much as a suite's.
