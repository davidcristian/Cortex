# The descent obligation stops at the suites

**Status:** open, fix when it bites
**Trigger:** a module under `scripts/tests/` descends a directory tree without filtering what it
finds against `SKIPPED_DIRS`, so a suite reads a file inside a vendored tree, a build output or a
tool cache. Both suites that descend one today do filter, so this is one search away from an
answer.
**Area:** repo-gates
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-gates.md)
**Verified:** 2026-09-10

Opened 2026-09-08 by the close of
[R-423](423-an-obligation-test-knows-a-caller-by-its-spelling.md), which made `treewalk.py` the one
descent under `scripts/` and held every module there to using it.

The set that obligation is compared over is `scripts/*.py`, which is what its predecessor scanned
and which leaves the suites beside those modules outside it. Two of them descend a tree of their
own: `test_loggernames.py` reads the brain's modules with a filtered `rglob`, and `test_treewalk.py`
lists `scripts/` to ask the question the obligation is. The first is deliberate and says so in its
own docstring: it walks the tree `logcalls.modules` walks so that the two answers can be compared,
and a walk that took its files from the same module would agree with whatever that module now
means. Both filter against the shared list, so nothing is wrong in the tree today.

**Why it was left.** Holding the suites to the shared descent would break the one test that has a
reason to descend independently, and excusing that one file by name is the shape of rule the close
this entry came from was written to remove: a search with an exception list is a search that stops
being read. The bite is also smaller here than in a gate. A suite that walked into `.venv` reads a
dependency's source and fails or slows down in its own run, which is loud, where a gate that walks
into one reports a fault about a file this repo does not own.

**What would close it.** Either widen the obligation to `scripts/tests/*.py` and give
`test_loggernames.py` a way to descend that is not an exception by name, an explicit second reader
in `treewalk.py` whose whole purpose is to be a second opinion; or record at ADR-0026 that the
suites are outside it on purpose, with the reason above, so the next reader of the obligation knows
the boundary is a decision rather than the edge of what the first version happened to scan.

## Trail

- 2026-09-08: opened by the close of
  [R-423](423-an-obligation-test-knows-a-caller-by-its-spelling.md), whose
  [ADR-0026 shaped-obligation addendum](../../adr/ADR-0026-prose-style-gates.md) records the
  descent's new home and the set the obligation is compared over.
- 2026-09-10: still not fired, and one of the two descents named here has moved to a plain glob.
  `test_loggernames.py` still walks the brain's packages with `rglob("*.py")` and still drops any
  module whose parts meet `SKIPPED_DIRS`. `test_treewalk.py` reads `scripts/` with a
  non-recursive `GATES.glob("*.py")`, which enters no subdirectory at all, so it has nothing to
  filter. The other suites that glob (`test_gitenv.py`, `test_composeservices.py`,
  `test_flagcheck.py`, `test_crosscheck.py`, `test_logsamples.py`) all take one named directory
  with a non-recursive pattern. No suite under `scripts/tests/` descends unfiltered.
