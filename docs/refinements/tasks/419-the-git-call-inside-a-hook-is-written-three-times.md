# The environment strip that makes a git call inside a hook honest is written out three times

**Status:** open, fix when it bites
**Trigger:** a fourth module needs to ask git something, or one of the three is edited by somebody
who does not know why the environment is rebuilt, which is the first time the copies cost more than
the lines they occupy.
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
