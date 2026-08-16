# Nothing reads the toolchain the coverage step prints

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-gates.md)
**Trigger:** a second toolchain-caused coverage failure, or the first one where reading the two printed versions is not enough to settle whether the toolchain moved.

Opened 2026-08-16 by the entry that declined to pin the coverage toolchain
([R-274](274-unpinned-nightly-drifts-the-coverage-gate.md)). `check-body` now prints
`rustc +nightly --version` and `cargo +nightly llvm-cov --version` before it measures, so a red run
in CI and a green one on this machine each name their own compiler and tool, and telling a
toolchain change from the commit under test is two lines read side by side rather than a local
bisect against two nightlies.

What that does not do is make anything read them. No side compares its versions against the
other's, so the comparison needs a person with two logs open. Nothing records which toolchain last
measured green, so after a drift the green half of the comparison has to be found rather than
looked up, and a CI log ages out on the runner's retention rather than on this repo's schedule.
The printing therefore removes the diagnosis cost and leaves the retrieval cost.

**Two shapes were considered and neither is worth its mechanism on one incident.** Failing the
gate when the two sides differ needs an expected version written down, which is the dated pin under
another name and carries the pin's expiry (a frozen nightly is overtaken by stable in about twelve
weeks) without buying its reproducibility, since cargo-llvm-cov is unpinned on both sides too.
Writing a stamp beside `body/coverage.json` and echoing it from `coverage_gate.py` would put the
last green toolchain in the gate's own output rather than in a log, which is the cheaper half of
the value; the cost is a second artifact the gate has to read, keep honest, and fail closed on when
it is missing, which is a gate of its own to write and to prove fires.
