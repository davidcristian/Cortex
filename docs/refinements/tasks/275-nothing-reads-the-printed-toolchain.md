# Nothing reads the toolchain the coverage step prints

**Status:** landed 2026-08-17
**Area:** repo-gates
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-gates.md)

Opened 2026-08-16 by the entry that declined to pin the coverage toolchain
([R-274](274-unpinned-nightly-drifts-the-coverage-gate.md)). `check-body` now prints `rustc +nightly
--version` and `cargo +nightly llvm-cov --version` before it measures, so a failing run in CI and a
passing one on this machine each name their own compiler and tool, and telling a toolchain change
from the commit under test is two lines read side by side rather than a local bisect against two
nightlies.

What that does not do is make anything read them. No side compares its versions against the other's,
so the comparison needs a person with two logs open. Nothing records which toolchain last measured a
passing run, so after a drift the passing half of the comparison has to be found rather than looked
up, and a CI log ages out on the runner's retention rather than on this repo's schedule. The
printing therefore removes the diagnosis cost and leaves the retrieval cost.

**Two shapes were considered and neither is worth its mechanism on one incident.** Failing the gate
when the two sides differ needs an expected version written down, which is the dated pin under
another name and carries the pin's expiry (a frozen nightly is overtaken by stable in about twelve
weeks) without buying its reproducibility, since cargo-llvm-cov is unpinned on both sides too.
Writing a stamp beside `body/coverage.json` and echoing it from `coverage_gate.py` would put the
last green toolchain in the gate's own output rather than in a log, which is the cheaper half of the
value; the cost is a second artifact the gate has to read, keep accurate, and fail closed on when it
is missing, which is a gate of its own to write and to prove fires.

**Closed 2026-08-17** ([ADR-0002 single-verdict addendum](../../adr/ADR-0002-toolchain-gates.md)).
Every claim above was re-derived before anything changed and all of it held, and re-deriving it
found the thing this file could not see: the printing had been placed above a failure that says
nothing. `check-body` carried `--fail-under-lines 100 --fail-under-regions 100` on the measurement
and then ran `coverage_gate.py`, which already gated those same two metrics plus branches. With the
report diverted by `--json --summary-only --output-path`, those flags exit 1 having printed no
metric, no percentage and no threshold, measured here at 346 lines of output and not one of them
about coverage. So the redundant copy of the threshold ran first and pre-empted the copy that
reports what failed, and the one incident on record reported an exit code under two version lines.

**What landed is smaller than either shape and does more.** The two flags came off, making
`coverage_gate.py` the single verdict, so a coverage failure now names its metric and its percentage
at all. And the attribution needed no stamp: the export already records its writer in
`cargo_llvm_cov.version` beside the llvm export format's `version`, both of which the gate now
requires, refusing a report that will not say what wrote it. The recipe hands over what it probed,
`--rustc` relayed into the verdict and `--llvm-cov` checked against the export's own record, so a
report the running tool did not write fails however good its numbers are. A passing run therefore
prints the toolchain that produced it, in the gate's own output, which is what the stamp shape
wanted.

**The comparison across the two sides stays declined**, on the argument the printing addendum
already gave: failing when they differ needs an expected version written down, which is the dated
pin under another name. The retrieval cost turned out smaller than this file assumed, since CI
installs the channel fresh on every run and rustc's version string carries the date, so a green CI
run's compiler is recoverable from when it ran.

## Trail

- 2026-08-16: opened as the residual of the toolchain-print addendum, which named the two versions
  in the log and left nothing reading them.
- 2026-08-17: landed. It became the removal of cargo-llvm-cov's own line and region thresholds,
  which failed without output and pre-empted the gate that reports the metric, plus an attribution
  the gate reads out of the export it already parses and checks against the tool the step probed. It
  opened [R-290](290-the-export-names-its-tool-not-its-compiler.md), which holds the half still
  relayed rather than checked: the export names its tool and never its compiler, and the compiler is
  the half that drifted.
