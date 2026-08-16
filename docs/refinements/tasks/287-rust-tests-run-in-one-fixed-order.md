# The Rust suite runs in one fixed order

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-gates.md)
**Trigger:** a Rust test that passes alone and fails inside `cargo test`, or any order-dependent flake in the body workspace.

Opened 2026-08-16 by the pass that made the shuffle standing in the other three suites
([ADR-0002 shuffle addendum](../../adr/ADR-0002-toolchain-gates.md)). Both Python suites now run
shuffled under a fixed seed and so does the overlay's Vitest suite. The Rust workspace does not,
and the reason is the toolchain rather than a decision anybody made.

**What is and is not already true.** `cargo test` runs a binary's tests in parallel threads, which
is easy to mistake for randomization and is not: threads decide when a test runs beside another,
not what order the list is handed out in. libtest has no shuffle option, so the order is the
collected one, stable across runs. Parallelism does buy something the Python suites do not have,
in that a test which depends on a sibling's leftover state is racing rather than reliably second,
so the dependency shows up as a flake instead of as a pass; but it shows up only when the state is
shared through something threads can both reach, and never for the ordinary case of a test that
needs its sibling to have run first.

**What would close it.** `cargo-nextest` has `--shuffle`, and it runs each test in its own process,
which is a stronger isolation than libtest's threads and would make the shuffle mean what it means
in pytest. The cost is a second test runner in the gate beside `cargo test` and `cargo llvm-cov`,
which is a real addition to a gate this repo keeps to one command per tree, and nextest's
relationship with `cargo llvm-cov` is its own question to settle rather than assume. Neither has
been costed, and no ordering defect has been seen in the Rust tree; this is written down so the
asymmetry between the two toolchains is a recorded state rather than an oversight.
