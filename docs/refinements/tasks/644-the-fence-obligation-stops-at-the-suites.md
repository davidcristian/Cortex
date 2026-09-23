# The fence obligation stops at the suites

**Status:** declined 2026-09-15
**Area:** repo-checks
**Origin:** [ADR-0062](../../adr/ADR-0062-shared-check-readers.md)

`markdownfences.py` is the one module under `scripts/` allowed to write a fence marker, and the test
that requires it compares over `scripts/*.py`, which leaves the suites beside those modules out.
They have to be out: seven of them write a fence marker, and every one of those markers is a fixture
rather than a reader. `test_logsamples.py` and `test_samplecheck.py` write a fenced sample in the
shapes the runbooks use, `test_commitlint.py` parametrizes the four ways a message may open a paste,
`test_headingshapes.py` and `test_backloganchors.py` each write a block containing a shell comment,
`test_rosternames.py` writes a fenced command into the page a roster is read out of, and
`test_markdownfences.py` writes the markers the shared reader is asked about. A suite that grew a
reader of its own would look the same to the comparison.

The cost of leaving it is smaller than in a module: a fence reader inside a suite would decide what
that suite's own fixtures mean, where a second reader in a module decides what a check reports about
the repo.

[R-610](610-the-descent-obligation-stops-at-the-suites.md) is the sibling entry, the same boundary
on the directory-walk rule for a different reason: there one suite has to descend independently,
here every suite has to write a marker.

**What closed it.** Declined, with the boundary written down per rule in
[ADR-0062](../../adr/ADR-0062-shared-check-readers.md) decision 8, which also names the
git-environment rule that does cover the suites.
`scripts/tests/test_markdownfences.py`'s docstring points at it. A rule by shape, counting a marker
that reaches a `re.compile`, a `startswith` or an `in` test as a reader and one inside a document
string as data, was refused: the requirement is over literals, so a module importing `MARKERS` and
testing a line against it is reported by nothing today, in a module as much as in a suite, and a
shape rule would enumerate the positions that count as reading while leaving that hole open. What
the requirement means is that the marker is written once, and a suite writing a fixture is not a
second definition of it.

What would reopen this is a suite found testing a line against a marker rather than writing one into
a document.

## History

- 2026-09-12: opened by the close of
  [R-445](445-three-checks-each-define-the-markdown-fence-for-themselves.md), whose
  [ADR-0062](../../adr/ADR-0062-shared-check-readers.md) decision 7 records the set the requirement
  is compared over and why the suites are not in it.
- 2026-09-14: still not a live problem, and the same correction the sibling entry has applies here.
  Seven suites write a fence marker and all 48 of their markers are fixtures; none tests a line for
  a marker. What the entry did not say is that the boundary is not the whole family's:
  `test_gitenv.py` compares over `[*SCRIPTS.glob("*.py"), *SCRIPTS.glob("tests/*.py")]`, so of the three
  requirements here one covers the suites and two do not. This entry and
  [R-610](610-the-descent-obligation-stops-at-the-suites.md) share a cause, the comparison set
  written per rule rather than once, and nothing else: widening this one needs a rule telling a
  marker that reaches a `re.compile`, a `startswith` or an `in` test from a marker inside a document
  string, and widening that one needs a second reader in `treewalk.py`.
- 2026-09-15: declined, alongside [R-610](610-the-descent-obligation-stops-at-the-suites.md). The
  count was taken again: seven suites write a fence marker, 65 literals on 42 lines, and every one
  of the 65 was classified by the syntax around it. None reaches a `re.compile`, a `startswith`, a
  `match` or a comparison. The reading that refused the shape rule also opened
  [R-669](669-the-fence-obligation-is-over-literals-only.md), the hole it names being a module's as
  much as a suite's.
