# The coverage step takes whatever nightly it finds

**Status:** done 2026-08-16
**Area:** repo-checks
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-checks.md)

The rust CI job installs `toolchain: nightly`, a channel rather than a dated toolchain, so the
branch-coverage step runs on whatever nightly exists the day the job runs while this host runs
whatever nightly it last installed. Nothing ties the two together and neither is recorded, so a
coverage failure caused by the toolchain looks at first like one caused by the commit under test.

That happened once, and ADR-0002's build-script exclusion is the repair. The check failed in CI at
99.40% lines on a one-line dependabot bump that could not move coverage, and passed at 100% on the
same commit here, because rustc began instrumenting Cargo build scripts somewhere between
1.98.0-nightly (2026-07-01), the nightly on this host, and 1.99.0-nightly (2026-08-10), the one CI
resolved. The fix excluded build scripts from the measurement, which addressed that one
instrumentation change rather than the difference that delivered it.

Closed 2026-08-16 ([ADR-0002](../../adr/ADR-0002-toolchain-checks.md) decision 11). Every claim
above was checked against the tree first and held, including the part this file could not know it
was right about: the two sides were apart on the day, this machine's `nightly` alias resolving to
rustc 1.98.0-nightly (2026-07-01) against a CI that resolves the day's.

The cheap half was done as written, widened by one line. `check-body` prints `rustc +nightly
--version` and `cargo +nightly llvm-cov --version` before it measures, the tool being the second
unfixed part this file did not name and the one the earlier incident had to hold at 0.8.7 by hand.
CI runs that same recipe, so one edit covers both sides.

Fixing the toolchain to a date is declined rather than deferred again. A dated version expires:
nightly runs two releases ahead of stable, so a version chosen today is overtaken by stable in
about twelve weeks, after which the coverage step compiles the body under an older compiler than
every other step and the first newly stabilized feature the workspace adopts fails under coverage
alone. That is this entry's own complaint reintroduced by its own fix, on a clock nobody services.
Two more reasons: fixing the compiler while the tool stays loose claims a reproducibility the step
does not have, and fixing the tool as well inverts the mismatch, since cargo-llvm-cov is the half
that has to track the compiler. What the printing does not do is make anything read the versions,
which is [R-275](275-nothing-reads-the-printed-toolchain.md).

## History

- 2026-08-11: Recorded as what was left over from the build-script coverage exclusion. The
  exclusion fixed the instrumentation change; this entry covers the version difference that
  produced it, reproduced by running the same command under both nightlies with cargo-llvm-cov held
  at 0.8.7.
- 2026-08-16: Closed. It became two version probes in `check-body` plus a recorded refusal to fix
  the version, and it opened [R-275](275-nothing-reads-the-printed-toolchain.md).
