# The environment strip that makes a git call inside a hook accurate is written out three times

**Status:** done 2026-08-24
**Area:** repo-checks
**Origin:** [ADR-0062](../../adr/ADR-0062-shared-check-readers.md)

Three modules in `scripts/` run a git command, and all three rebuild the environment the same way,
dropping every variable whose name starts with `GIT_`. All three have a comment saying why: these
checks run inside hooks, git exports `GIT_DIR` there, and that variable takes precedence over the
`-C` the call passes, so an inherited one answers about whatever repository git is mid-commit in.
`bindcheck.py` asks whether a path is tracked and whether it is ignored, `commitlint.py` reads a
message, and `dashcheck.py` asks for the ignored listing. The suites repeat it a fourth and fifth
time in their own fixtures.

This is not a value written twice, so the constant scan has nothing to say about it. It is a
correctness detail with no single home, and the failure it prevents is unreported: a caller that
omits the strip gets an answer about the wrong repository and nothing says so.

The first decision is whether the shared thing is the environment or the call. The environment
alone is one function and leaves each check its own argv, which suits three callers asking
different questions. A shared call is worse: they need different exit code handling,
`check-ignore` answering with 1 for a legitimate no, so a shared runner would grow a parameter per
caller.

## History

- 2026-08-24: opened by the close of
  [R-411](411-the-dash-ban-reads-a-working-tree-not-a-commit.md), which made `dashcheck.py` the
  third module here to run a git command.
- 2026-08-24: closed as `scripts/gitenv.py`, one constant and one function, read by the three
  checks and by the three suites. The count above was low: the strip was written out six times, not
  five, `test_bindcheck.py`, `test_commitlint.py` and `test_dashcheck.py` each having a fixture of
  its own. The first question went the way this entry argued, and reading the three call sites
  settled it: they agree on nothing but the environment, since `check-ignore` answers 1 for a
  legitimate no, the two walking checks raise their own exception types, and `commitlint.py`
  answers a missing git with False rather than an exception, because a commit-msg hook that cannot
  run git must not block the commit. A shared runner would have taken an allowed-codes set, an
  exception factory and an `OSError` policy, one parameter per caller. A helper nobody is obliged
  to call being no fix, each check is now required to call it by a test that exports a `GIT_DIR`
  naming no repository over a real git and demands the right answer anyway, and the trigger this
  entry had, a fourth caller, is covered by a test that any file here writing a git argv also
  writes the call that hands it an environment. Six planted mutations; the last of them is a check
  writing a correct copy of the strip again, which every behaviour test passes and only that
  obligation catches. One residue, shared with the close that added the same obligation over the
  tree walks: [R-423](423-the-two-obligation-tests-recognize-a-caller-by-how-it-is-written.md), the test finding
  its callers by how they are written.
