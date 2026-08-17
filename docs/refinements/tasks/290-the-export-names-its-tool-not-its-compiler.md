# The coverage export names its tool and never its compiler

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-gates.md)
**Trigger:** a coverage failure where the relayed `rustc` line is not enough to settle whether the
compiler moved, or cargo-llvm-cov recording the compiler in its export, which would make the check
free.

Opened 2026-08-17 by the entry that made the coverage verdict read its own toolchain
([R-275](275-nothing-reads-the-printed-toolchain.md)). `coverage_gate.py` now attributes the
numbers it judges, and the two halves of that attribution are not equally strong. The tool half is
checked: the export records its writer in `cargo_llvm_cov.version`, the recipe passes what
`cargo +nightly llvm-cov --version` printed, and a disagreement fails the gate, because it means
the report being judged is not the one this run wrote. The compiler half is only relayed. Nothing
in a cargo-llvm-cov export names the rustc that instrumented the build, so `--rustc` is a string
the recipe hands over and the gate prints beside its verdict, believed on the recipe's word.

That is the weaker half of the pair and it is the half that has actually drifted. The build-script
incident was a compiler change, rustc moving from 1.98.0-nightly to 1.99.0-nightly and beginning to
instrument `build.rs`, with cargo-llvm-cov held at 0.8.7 throughout. So the gate checks the version
that stayed put and takes the version that moved on trust.

**Nothing cheap closes it.** The recipe probes the compiler in the same shell that invokes the
gate, so a wrong string there would have to come from a wrong `+nightly` resolution, and re-probing
inside the gate would put a real toolchain call inside a pure gate module, which is the boundary
AGENTS.md gate 3 draws. Reading the instrumented binaries' own metadata would tie this gate to a
profile format nobody else here reads. Recording an expected compiler is the dated pin, declined
twice already on its expiry. The honest shape, if the trigger ever fires, is to stop treating the
relayed string as attribution and start treating it as a claim the gate can refuse: require it to
parse as a nightly version, and require the date it carries to be no older than the one the last
green run recorded, which needs somewhere to record that and is the stamp R-275 costed and did not
build.
