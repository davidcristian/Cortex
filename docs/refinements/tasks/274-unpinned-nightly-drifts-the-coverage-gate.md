# The coverage gate's nightly is a channel, so upstream drift breaks it

**Status:** landed 2026-08-16
**Area:** repo-gates
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-gates.md)

The rust CI job installs `toolchain: nightly`, a channel rather than a dated toolchain, so the
branch-coverage step runs on whatever nightly exists the day the job runs while this host runs
whatever nightly it last installed. Nothing ties the two together, and neither is recorded
anywhere, so a gate failure caused by the toolchain is indistinguishable at first read from one
caused by the commit under test.

That is not hypothetical: it has happened once, and the ADR-0002 build-script addendum is the
repair. The gate failed in CI at 99.40% lines on a one-line dependabot bump that could not
possibly move coverage, and passed at 100% on the same commit here, because rustc began
instrumenting Cargo build scripts somewhere between 1.98.0-nightly (2026-07-01), the nightly on
this host, and 1.99.0-nightly (2026-08-10), the one CI resolved. The fix excluded build scripts
from the measurement, which is correct on its own terms, but it addressed that one instrumentation
change rather than the drift that delivered it.

**Why it is deferred rather than pinned now.** A dated pin makes CI and the host agree and puts the
toolchain in the diff, so an instrumentation change arrives as a deliberate bump with a green or
red run attached to it. The cost is that the pin goes stale silently: dependabot bumps action SHAs
and cannot bump a rustup channel string, so nothing would ever raise the nightly again, and the
gate would drift the other way, measuring branch coverage on an increasingly old compiler until
something else forced the issue. The middle option worth naming is pinning CI to a date and
recording the same date in the machine-setup runbook, which keeps the two sides equal and makes
staleness visible in one place, at the cost of a manual bump nobody is scheduled to make.

The cheaper half of the value is available without deciding any of that: the coverage step could
print `rustc +nightly --version` before it runs, so a future failure names its toolchain in the log
instead of requiring a local bisect against two nightlies to find it. That is worth doing whenever
this entry is next opened, independent of the pin question.

**Closed 2026-08-16** ([ADR-0002 toolchain-print
addendum](../../adr/ADR-0002-toolchain-gates.md)). Every claim above was re-derived from the tree
before anything changed and all of it still held, including the part this file could not know it
was right about: the two sides are apart *today*, this machine's `nightly` alias resolving to
rustc 1.98.0-nightly (2026-07-01) against a CI that resolves the day's.

The cheaper half landed as written, widened by one line. `check-body` prints
`rustc +nightly --version` and `cargo +nightly llvm-cov --version` before it measures, the tool
being the second unpinned part this file did not name and the one the earlier incident had to hold
at 0.8.7 by hand before it could say anything about the compiler. CI runs that same recipe, so one
edit covers both sides.

**The pin is declined, not deferred again**, on an argument this file did not have. A dated pin
expires: nightly runs two releases ahead of stable, so a pin taken today is overtaken by stable in
about twelve weeks, after which the coverage step compiles the body under an older compiler than
every other step and the first newly stabilized feature the workspace adopts fails under coverage
alone. That is this entry's own complaint reintroduced by its own fix, on a clock nobody services.
Two more: pinning the compiler while the tool stays unpinned sells a reproducibility the step does
not have, and pinning the tool as well inverts the mismatch, since cargo-llvm-cov is the half that
has to track the compiler. What the printing does not do is make anything *read* the versions,
which is [R-275](275-nothing-reads-the-printed-toolchain.md).

## Trail

- 2026-08-11: Recorded as the residual of the build-script coverage exclusion. The exclusion fixed
  the instrumentation change; this entry holds the drift that produced it, reproduced by running
  the same gate command under both nightlies with cargo-llvm-cov held at 0.8.7.
- 2026-08-16: closed. It became two version probes in `check-body` plus a recorded refusal to pin,
  and it opened [R-275](275-nothing-reads-the-printed-toolchain.md), which holds the half the
  probes leave undone: the versions are printed and no gate reads them.
