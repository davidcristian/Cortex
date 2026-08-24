# The environment strip that makes a git call inside a hook honest is written out three times

**Status:** landed 2026-08-24
**Area:** repo-gates
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-gates.md)

Opened 2026-08-24 by the close of
[R-411](411-the-dash-ban-reads-a-working-tree-not-a-commit.md), which made `dashcheck.py` the third
module in `scripts/` to run a git command.

All three rebuild the environment the same way, dropping every variable whose name starts with
`GIT_`, and all three carry a comment saying why: these gates run inside hooks, git exports
`GIT_DIR` there, and that variable outranks the `-C` the call passes, so an inherited one answers
about whatever repository git is mid-commit in. `bindcheck.py` asks whether a path is tracked and
whether it is ignored, `commitlint.py` reads a message, and `dashcheck.py` now asks for the ignored
listing. The suites duplicate it a fourth and fifth time in their own fixtures.

This is not a value spelled twice, so the constant scan has nothing to say about it. It is a
correctness detail with no single home, and the failure it prevents is silent: a caller that forgets
the strip gets an answer about the wrong repository and never learns it.

**Why it was left.** The close was about what the dash ban reads, and moving a shared helper out of
two other gates would have been a second change riding along with a decision about a rule. Three
copies of five lines is also not yet a cost anybody has paid.

**What would close it.** Decide whether the shared thing is the environment or the call. The
environment alone is one function and leaves each gate its own argv, which is honest because the
three ask different questions. The call is more tempting and worse: the three want different exit
code handling, `check-ignore` answering with 1 for a legitimate no, so a shared runner would grow a
parameter per caller. If a module lands, it takes the fixtures too, since a test that rebuilds the
environment by hand can drift from the gate it tests.

## Trail

- 2026-08-24: opened by the close of
  [R-411](411-the-dash-ban-reads-a-working-tree-not-a-commit.md), which made `dashcheck.py` the
  third module here to run a git command.
- 2026-08-24: landed as `scripts/gitenv.py`, one constant and one function, read by the three
  gates and by the three suites. **The count above was low**: the strip was written out six times,
  not five, `test_bindcheck.py`, `test_commitlint.py` and `test_dashcheck.py` each carrying a
  fixture of its own. The decide-first question went the way this entry argued, and reading the
  three call sites is what settled it: they agree on nothing but the environment, since
  `check-ignore` answers 1 for a legitimate no, the two walking gates raise their own exception
  types, and `commitlint.py` answers a missing git with False rather than an exception, because a
  commit-msg hook that cannot run git must not block the commit. A shared runner would have taken
  an allowed-codes set, an exception factory and an `OSError` policy, one parameter per caller.
  A helper nobody is obliged to call being no fix, each gate is now held to calling it by a test
  that exports a `GIT_DIR` naming no repository over a real git and demands the right answer
  anyway, and the trigger this entry carried, a fourth caller, is held by a test that any file
  here spelling a git argv also spells the call that hands it an environment. Six planted
  mutations, tabled in the ADR-0026 git-environment addendum; the last of them is a gate writing
  a correct copy of the strip again, which every behaviour test passes and only that obligation
  catches. One residue, shared with the close that landed the same shape of obligation over the
  tree walks: [R-423](423-an-obligation-test-knows-a-caller-by-its-spelling.md), the test finding
  its callers by how they are spelled.
