# The descent obligation stops at the suites

**Status:** declined 2026-09-15
**Area:** repo-gates
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-checks.md)

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
  [ADR-0026 shaped-obligation addendum](../../adr/ADR-0026-prose-style-checks.md) records the
  descent's new home and the set the obligation is compared over.
- 2026-09-10: still not fired, and one of the two descents named here has moved to a plain glob.
  `test_loggernames.py` still walks the brain's packages with `rglob("*.py")` and still drops any
  module whose parts meet `SKIPPED_DIRS`. `test_treewalk.py` reads `scripts/` with a
  non-recursive `GATES.glob("*.py")`, which enters no subdirectory at all, so it has nothing to
  filter. The other suites that glob (`test_gitenv.py`, `test_composeservices.py`,
  `test_flagcheck.py`, `test_crosscheck.py`, `test_logsamples.py`) all take one named directory
  with a non-recursive pattern. No suite under `scripts/tests/` descends unfiltered.
- 2026-09-14: still not fired, and one claim this entry rests on is wrong. No suite under
  `scripts/tests/` descends a tree unfiltered: `test_loggernames.py` is the only recursive
  descent there, at line 210, and it still drops any module whose parts meet `SKIPPED_DIRS`;
  every other glob in that directory is non-recursive. What the entry does not say is that a
  sibling obligation in the same family already runs over the suites.
  `test_gitenv.py` compares its set over `[*GATES.glob("*.py"), *GATES.glob("tests/*.py")]`, and
  its docstring records that it was widened to reach a suite: the one beside the skip list runs
  git with an argv the formatter wrote one item per line. So three obligations read modules
  through `gatecalls.py` and `markdownfences.py`, and they do not agree on their boundary: the
  git-environment one covers the suites, this one and the fence one do not.

  That weakens the second branch as this entry states it. Recording at the origin that "the
  suites are outside it on purpose" cannot be written as a rule about obligations here, because
  one of them is not. What is writable is the narrower decision: this obligation stops at the
  suites because widening it would break the one suite with a reason to descend independently,
  and the git-environment obligation had no such suite to break. Whichever branch is taken should
  name the third obligation, so the next reader meets the inconsistency where it is decided
  rather than by grepping for the set expression.
- 2026-09-15: declined, with the second branch taken and narrowed as the reading above asked.
  The search was run once more and still returns nothing: the only descent under `scripts/tests/`
  is `test_loggernames.py`'s `rglob` at line 210, and it still drops any module whose parts meet
  `SKIPPED_DIRS`. Every other glob there is a non-recursive listing of one directory.

  What is written down instead is the boundary, per obligation, in the
  [ADR-0026 addendum on where each obligation stops](../../adr/ADR-0026-prose-style-checks.md),
  which names the git-environment obligation that does cover the suites so the next reader meets
  the inconsistency where it is decided. The first branch is refused on its own terms: the
  independence `test_loggernames.py` needs is of the descent itself, its guard comparing a reading
  against `logcalls.modules`, which takes its files from `treewalk.walk_files`, so a second reading
  taken from there too would come back empty beside the first if that walk ever stopped finding
  modules. A second descent in `treewalk.py` to supply that independence puts two implementations
  of one walk in the module written to hold one, and the second has a single caller.
  `scripts/tests/test_treewalk.py`'s docstring now carries the pointer.

  What would reopen this is a second suite with a reason to descend independently, which would make
  the exception a class that can be named as one rather than a single file.
