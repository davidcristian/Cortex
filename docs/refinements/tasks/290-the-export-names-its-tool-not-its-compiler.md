# The coverage export names its tool and never its compiler

**Status:** declined 2026-08-18
**Area:** repo-checks
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-checks.md)

Opened 2026-08-17 by the entry that made the coverage result read its own toolchain
([R-275](275-nothing-reads-the-printed-toolchain.md)). `rustcoverage.py` attributes the numbers it
judges, and the two halves of that attribution are not equally strong. The tool half is checked:
the export records its writer in `cargo_llvm_cov.version`, the recipe passes what `cargo +nightly
llvm-cov --version` printed, and a disagreement fails the check, because it means the report being
judged is not the one this run wrote. The compiler half is only relayed. Nothing in a cargo-llvm-cov
export names the rustc that instrumented the build, so `--rustc` is a string the recipe passes on
and the check prints beside its result, taken on the recipe's word. That is the weaker half, and it
is the half that changed: the build-script incident was rustc moving from 1.98.0-nightly to
1.99.0-nightly and beginning to instrument `build.rs`, with cargo-llvm-cov held at 0.8.7
throughout.

Declined, because neither half of its own trigger leads anywhere worth a mechanism:

- The shape this entry proposed cannot work here. It asks for the relayed string to be refused
  unless it parses as a nightly no older than the one the last passing run recorded, which needs
  somewhere to record it. The two sides deliberately resolve different nightlies, the host at
  1.98.0-nightly and CI at whatever the channel is on the day, so a committed record would fail the
  host on every run after CI recorded a newer date, and a per-machine ignored record is absent on a
  fresh CI checkout, which is the run that matters.
- The other half would buy a check that cannot fail. If cargo-llvm-cov ever recorded the compiler,
  the check would compare a relayed string against a recorded one for a build that ran seconds
  earlier in the same shell, where the only way to disagree is a `+nightly` that resolved
  differently between two adjacent commands.

One route nobody had costed, recorded so the knowledge survives: cargo does record the compiler of
the instrumented build, in `body/target/llvm-cov-target/.rustc_info.json`, whose outputs block held
`rustc 1.98.0-nightly (4c9d2bfe4 2026-07-01)` for this machine's run when it was read on
2026-08-18. Reading it is a build-artifact read, the same category as reading `coverage.json`, so
it does not cross the boundary that keeps real toolchain calls out of a pure module. It is still
not worth doing: it buys the same near-empty proposition and would tie a check to an undocumented
cargo cache layout.

What actually went wrong in the build-script incident was the two sides running compilers weeks
apart, and the only mechanism that catches that is an expected version written down, which is the
dated toolchain this decision has now declined twice on its expiry cost.

## History

- 2026-08-17: Opened by the entry that made the coverage result read its own toolchain, as the half
  of the attribution that is relayed rather than checked.
- 2026-08-18: Declined on the findings above. Reading this also turned up an unrelated hole in the
  same module, filed as [305](305-optional-toolchain-relays.md). The reasoning is recorded at the
  origin decision.
