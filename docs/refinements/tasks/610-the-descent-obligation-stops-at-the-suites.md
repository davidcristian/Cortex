# The descent obligation stops at the suites

**Status:** declined 2026-09-15
**Area:** repo-checks
**Origin:** [ADR-0062](../../adr/ADR-0062-shared-check-readers.md)

`treewalk.py` is the one directory walk under `scripts/`, and the test that requires every module
there to use it compares over `scripts/*.py`. That leaves the suites beside those modules out.
One of them descends on its own: `test_loggernames.py` walks the brain's packages with `rglob`, on
purpose, so its reading can be compared against the one `logcalls.modules` produces. It filters
against the shared skip list, so nothing in the tree is wrong today.

Widening the requirement to `scripts/tests/*.py` would break that test, and excusing it by name is
the kind of rule with an exception list that the earlier work removed. The cost of leaving it is
small: a suite that walked into `.venv` reads a dependency's source and fails or slows down in its
own run, where a check that did the same reports a fault about a file this repo does not own.

Declined instead of widened, and the boundary is written down per requirement in
[ADR-0062](../../adr/ADR-0062-shared-check-readers.md) decision 8. What would reopen it is a second
suite with a reason to descend independently, which would make the exception a class rather than a
single file.

## History

- 2026-09-08: opened by the close of
  [R-423](423-an-obligation-test-knows-a-caller-by-its-spelling.md), which made `treewalk.py` the
  one descent under `scripts/`.
- 2026-09-10: not yet a problem. `test_loggernames.py` still walks the brain's packages with
  `rglob("*.py")` and drops any module whose parts meet `SKIPPED_DIRS`. Every other glob under
  `scripts/tests/` reads one named directory without recursing.
- 2026-09-14: one claim here was wrong. A sibling requirement in the same family already covers the
  suites: `test_gitenv.py` compares over `[*GATES.glob("*.py"), *GATES.glob("tests/*.py")]`. So the
  three requirements that read modules through `scriptcalls.py` and `markdownfences.py` disagree
  about their boundary, and no rule about all of them can be written. What is writable is the
  narrower reason: this one stops at the suites because widening it breaks the one suite that has to
  descend independently.
- 2026-09-15: declined. The search was run once more and still finds only `test_loggernames.py`'s
  `rglob` at line 210, which drops any module whose parts meet `SKIPPED_DIRS`. Giving that test a
  second walk inside `treewalk.py` was refused: its guard compares a reading against
  `logcalls.modules`, which takes its files from `treewalk.walk_files`, so a second reading taken
  from there would come back empty beside the first if that walk ever stopped finding modules, and
  a second implementation of one walk with a single caller does not belong in the module written to
  hold one. `scripts/tests/test_treewalk.py`'s docstring points at the decision.
