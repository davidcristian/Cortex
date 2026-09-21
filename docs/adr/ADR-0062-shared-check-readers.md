# ADR-0062: Shared readers for the repo checks: the tree walk, git's environment and code fences

**Status:** Accepted (2026-09-15)

## Context

The scans under `scripts/` answer the same few questions over and over: which files under a root to
read, how to run `git` from inside a pre-commit hook so it answers about the right repository, and
whether a markdown line opens or closes a fenced block. Each check that needed an answer first wrote
its own. Copies that agree are invisible to every behaviour test, so the one that changes is found
late: the anchor scan once had a hand-written twin of the dash ban's skip list, three checks wrote
the fence pattern for themselves, and the git environment strip was written out six times. A shared
answer only fixes this if every caller is required to use it, so each one here comes with a test
that reads the callers.

The `scripts/` toolchain is checked like the others (100% coverage, pyright strict), and a check
that lists what it measures is blind to a new module nobody added to the list.

## Decision

### The toolchain measures the tree

1. **`scripts/pyproject.toml` measures the tree, not a list.** pytest-cov runs `--cov=.`, with
   `tests/*` and `.venv/*` omitted, so a module no test imports reports 0% and fails the 100%
   threshold; pyright's `include` is `"."` with explicit excludes. Escaping either check takes a
   written exclusion, never a forgotten addition.

### One tree walk

2. **Every reader that descends a tree gets its files from `scripts/treewalk.py`.**
   `walk_files(root, also_skip=..., enter=...)` yields every regular file under `root`, never
   entering a skipped tree; `also_skip` adds names (the line cap's `tests` and `_generated` are the
   only addition) and `enter` is asked about each remaining directory (the dash ban's ignored
   directories). The line cap, the dash ban, the anchor scan, the compose walk, the log-call reader,
   the log-sample check, the asserted-line reader and the settings reader are all handed their files
   by it.

3. **The skip list is `scripts/skippeddirs.py`, and it is deliberately not `.gitignore`.**
   `SKIPPED_DIRS` holds eleven names: vendored trees, build output, tool caches, the archive of
   measurement runs and the object database. Nine of them restate a rule git already applies. `.git`
   is never reported ignored, and `coverage` is ignored only under `body/app/`, so a walk that
   trusted git alone would enter the object database and read a coverage report anywhere else.
   Making the line cap, the anchor scan and the compose walk ask git would also stop `just check`
   running on a tree that is not a git working tree, to save nine names that cost nothing and prune
   before any question is asked.

4. **The list is compared with git in both directions.** Outward, the suite asks git about every
   name, under the repo's own ignore rules alone, and asserts the split (nine restatements; `.git`
   and `coverage` outside them). Inward, it lists the directories git ignores that exist in the
   checkout, drops those a name already prunes, and reports any that holds a file a reader would
   open: the three whole-repo readers are asked by suffix, and the three readers scoped to a subtree
   are asked for the files they read (`logcalls.modules`, `samplecheck.runbooks`,
   `assertedlines.suite_of`), since two of them reach files the suffix readers do not.
   `measurements` joined the list when that check found archived measurement scripts counted by the
   line cap.

### One environment for git

5. **Every git call is handed `gitenv.git_env()`, and keeps its own argv.** Inside a hook, git
   exports `GIT_DIR` and its relatives for the repository being committed, so a check asking about
   another tree (or a suite's temporary repository) must drop every variable starting `GIT_`; the
   underscore is part of the prefix so `GITHUB_ACTIONS` survives. The environment is one fact; the
   calls differ in everything else (`check-ignore` answers 1 for a legitimate no, a non-zero from
   `ls-files` is a failure, `commitlint.py` answers an `OSError` with "cannot disprove"), so a
   shared runner would take a parameter per caller. The suites' fixtures import the same function.

### One definition of a fence

6. **What a code fence is lives in `scripts/markdownfences.py`.** `MARKERS` defines the two markers
   once. `Fences()` reads a document, since which block a line sits in is state no single line
   holds: `bounds(line)` says whether a line opened or closed a block, `inside` where the reading
   stands, and `closes(line)` whether a line would close the open block. A marker may be indented to
   any width and have an info string; a block closes only on a marker of the same character at least
   as long as the opener, so a four-backtick block holds a three-backtick line as text. The anchor
   scan, the commit hook and the log-sample check all read it. `rosternames.py` does not strip
   fences before cutting a roster out of a passage, because the repo map is a roster written inside
   a fenced block.

### The tests read the calls

7. **Each shared answer has a test that requires every caller to use it, compared as set equality.**
   `scripts/scriptcalls.py` reads what a module calls out of its syntax: `tree_reads` returns every
   call that descends a tree (`walk` and `rglob` always, `glob` or `iglob` unless the pattern is a
   literal naming one directory's entries, `ast.walk` told apart by the module it is called on), and
   `git_calls` every call handed a git argv, written inline or assigned to a name above it, with the
   function its `env=` keyword calls. A form it was not taught is treated as a tree descent, so it
   fails and somebody reads the report. The requirements are: the modules that descend a tree are
   `{treewalk.py}`; every git call is handed `git_env`; and the modules that write a fence marker in
   code, docstrings excepted, are `{markdownfences.py}` (`markdownfences.spelled`). A reader that
   finds nothing fails an equality as surely as a second copy does.

8. **How far each test reads is decided.** The git test reads `scripts/*.py` and
   `scripts/tests/*.py`, because a suite's fixture running git against the wrong repository fails
   somewhere unrelated. The tree and fence tests read `scripts/*.py` only. `test_loggernames.py`
   descends the brain's packages on its own deliberately: it compares two readings of one tree, and
   a second reading taken through `walk_files` would come back empty beside the first if that walk
   broke. In a suite, a fence marker is the document under test rather than a reader of one. Either
   boundary moves when a second suite needs an independent tree walk, or a suite is found testing a
   line against a marker.

## Consequences

- A new reader, git call or fence reader that does not use the shared answer fails the `scripts/`
  suite, even when it behaves identically.
- The dash ban alone asks git what it ignores ([ADR-0026](ADR-0026-prose-style-checks.md)); the other
  walks run on any directory.
- A newly ignored tree holding a readable file is reported by the inward check rather than found
  when a check reports a fault about a file the repo does not ship.

## Alternatives rejected

- **Reducing `SKIPPED_DIRS` to `.git` and trusting `.gitignore`.** It loses `coverage` outside
  `body/app/` and makes three more checks refuse a directory that is not a git working tree.
- **A shared git runner.** Every caller would pass its own codes, exception and `OSError` policy.
- **Recognizing a caller by searching for text** (`["git", `, `dirnames[:]`). A formatter splitting
  an argv, a filtered `rglob`, or a second call in one file each passed such a search unchecked.

## Related

- [ADR-0026](ADR-0026-prose-style-checks.md) (the dash ban and the commit hook),
  [ADR-0045](ADR-0045-documented-log-lines.md) (the log-sample check),
  [ADR-0044](ADR-0044-document-rosters.md) (the roster reader),
  [ADR-0039](ADR-0039-backlog-per-task.md) (the anchor scan).
- [repo checks](../modules/repo-checks.md).
