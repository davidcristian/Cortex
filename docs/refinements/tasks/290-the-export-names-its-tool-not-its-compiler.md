# The coverage export names its tool and never its compiler

**Status:** declined 2026-08-18
**Area:** repo-gates
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-gates.md)

Opened 2026-08-17 by the entry that made the coverage verdict read its own toolchain
([R-275](275-nothing-reads-the-printed-toolchain.md)). `coverage_gate.py` attributes the numbers it
judges, and the two halves of that attribution are not equally strong. The tool half is checked: the
export records its writer in `cargo_llvm_cov.version`, the recipe passes what `cargo +nightly
llvm-cov --version` printed, and a disagreement fails the gate, because it means the report being
judged is not the one this run wrote. The compiler half is only relayed. Nothing in a cargo-llvm-cov
export names the rustc that instrumented the build, so `--rustc` is a string the recipe hands over
and the gate prints beside its verdict, taken on the recipe's word. That is the weaker half of the
pair and it is the half that has actually drifted: the build-script incident was rustc moving from
1.98.0-nightly to 1.99.0-nightly and beginning to instrument `build.rs`, with cargo-llvm-cov held at
0.8.7 throughout.

All of that was re-derived on 2026-08-18 and holds exactly, this machine's real export carrying
`cargo_llvm_cov` and the export format and nothing about a compiler.

**Declined, because neither half of its own trigger leads anywhere worth a mechanism.**

**The shape this entry proposed cannot work in this repo.** It asks for the relayed string to be
refused unless it parses as a nightly whose date is no older than the one the last green run
recorded, and that needs somewhere to record it. The two sides of this project deliberately resolve
different nightlies, the host at 1.98.0-nightly and CI at whatever the channel is on the day. A
committed stamp would therefore fail the host on every run after CI recorded a newer date, and a
per-machine ignored stamp is absent on a fresh CI checkout, which is the run that matters. The
proposal fails on both sides, which was not known when the file was written.

**The other half of the trigger would buy a gate that cannot fail.** If cargo-llvm-cov ever
recorded the compiler, the check would compare a relayed string against a recorded one for a build
that ran seconds earlier in the same shell, where the only way to disagree is a `+nightly` that
resolved differently between two adjacent commands. A check that cannot fail is itself a defect by
this repo's own rule.

**One route nobody had costed, recorded so the knowledge survives.** Cargo does record the compiler
of the instrumented build, in `body/target/llvm-cov-target/.rustc_info.json`, whose outputs block
held `rustc 1.98.0-nightly (4c9d2bfe4 2026-07-01)` for this machine's run when it was read on
2026-08-18. Reading it is a build-artifact read, the same category as reading `coverage.json`, so
it does not cross the boundary that keeps real toolchain calls out of a pure gate module. It is
still not worth doing: it buys the same near-empty proposition as above and would bind a gate to an
undocumented cargo cache layout.

**And what actually drifted is a different problem with a known answer.** The failure in the
build-script incident was the two sides running compilers weeks apart, and the only mechanism that
catches that is an expected version written down, which is the dated pin this ADR has now declined
twice on its expiry cost.

## Trail

- 2026-08-17: Opened by the entry that made the coverage verdict read its own toolchain, as the
  half of the attribution that is relayed rather than checked.
- 2026-08-18: Declined on a re-derivation which found the entry's own proposed closure unworkable
  here, since the host and CI run different nightlies by design and a stamp fails on one side or is
  absent on the other. The cargo-written compiler record is noted above as the one cheap route, and
  rejected for buying a check that cannot fail. Reading this also turned up an unrelated hole in the
  same module, filed as [305](305-optional-toolchain-relays.md). The reasoning is recorded at the
  origin decision.
