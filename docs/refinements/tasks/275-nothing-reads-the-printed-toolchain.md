# Nothing reads the toolchain the coverage step prints

**Status:** done 2026-08-17
**Area:** repo-checks
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-checks.md)

Opened 2026-08-16 by the entry that declined to fix the coverage toolchain to a date
([R-274](274-unpinned-nightly-drifts-the-coverage-gate.md)). `check-body` prints `rustc +nightly
--version` and `cargo +nightly llvm-cov --version` before it measures, so a failing run in CI and a
passing one on this machine each name their own compiler and tool. What that does not do is make
anything read them: no side compares its versions against the other's, and nothing records which
toolchain last measured a passing run, so after a difference appears the passing half has to be
found rather than looked up.

Closed 2026-08-17 ([ADR-0002](../../adr/ADR-0002-toolchain-checks.md) decisions 12 and 13). Checking
the claims first found the thing this file could not see: the printing had been placed above a
failure that says nothing. `check-body` passed `--fail-under-lines 100 --fail-under-regions 100` to
the measurement and then ran `coverage_gate.py`, which already checked those same two metrics plus
branches. With the report diverted by `--json --summary-only --output-path`, those flags exit 1
having printed no metric, no percentage and no threshold, measured here at 346 lines of output and
not one of them about coverage. So the redundant copy of the threshold ran first and pre-empted the
copy that reports what failed, and the one incident on record reported an exit code under two
version lines.

What was built is smaller than either shape considered and does more. The two flags came off,
making `coverage_gate.py` the single result, so a coverage failure now names its metric and its
percentage. And the attribution needed no extra file: the export already records its writer in
`cargo_llvm_cov.version` beside the llvm export format's `version`, both of which the check now
requires, refusing a report that will not say what wrote it. The recipe passes on what it probed,
`--rustc` relayed into the result and `--llvm-cov` compared against the export's own record, so a
report the running tool did not write fails however good its numbers are. A passing run therefore
prints the toolchain that produced it, in the check's own output.

Comparing the two sides stays declined, on the argument ADR-0002 decision 11 already gave: failing
when they differ needs an expected version written down, which is the dated version under another
name. The retrieval cost turned out smaller than this file assumed, since CI installs the channel
fresh on every run and rustc's version string contains the date, so a green CI run's compiler is
recoverable from when it ran.

## History

- 2026-08-16: Opened by the change that printed the toolchain, which named the two versions in the
  log and left nothing reading them.
- 2026-08-17: Closed. It became the removal of cargo-llvm-cov's own line and region thresholds,
  which failed without output and pre-empted the check that reports the metric, plus an attribution
  read out of the export the check already parses. It opened
  [R-290](290-the-export-names-its-tool-not-its-compiler.md): the export names its tool and never
  its compiler, and the compiler is the half that changed.
