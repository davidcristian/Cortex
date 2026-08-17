# The Rust suite runs in one fixed order

**Status:** landed 2026-08-17
**Area:** repo-gates
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-gates.md)

Opened 2026-08-16 by the pass that made the shuffle standing in the other three suites, recording
the Rust workspace's fixed order as a known asymmetry rather than an oversight. It rested on one
factual claim, that libtest has no shuffle option and the order it hands out is therefore the
collected one, and that claim was wrong. libtest has `--shuffle` and `--shuffle-seed SEED`. They
are unstable, so stable rejects them and nightly rejects them too until `-Z unstable-options`
precedes them, which is how reading `cargo test -- --help` on stable leads to the conclusion the
entry drew.

So the costed alternative the entry described, adopting `cargo-nextest` as a second test runner
beside `cargo test` and `cargo llvm-cov` and settling its relationship with coverage, was never
needed. Nothing joins the gate. `check-body`'s coverage step is already nightly and already runs
the whole workspace, so it carries `-- -Z unstable-options --shuffle-seed=104729` and `just check`
now runs the Rust suite twice in two different orders, alphabetically on stable and permuted on
nightly, both of which must pass. `just shuffle [seed]` gained a fourth arm.

The entry's other paragraph, on parallelism being interleaving rather than randomization, holds and
is now a recorded limit of the shuffle rather than an argument against it: libtest permutes
dispatch order into as many threads as the machine has, so pairs closer together than the thread
count race either way and only pairs further apart are genuinely redrawn. Two things the entry did
not anticipate are recorded at the origin: libtest re-draws a binary's whole permutation whenever
its test list grows, which is not how `pytest-randomly` behaves and which gives the Rust tree for
free what [R-288](288-nothing-schedules-the-shuffle-sweep.md) wants a schedule for elsewhere, and a
test failure under the coverage step is loud and names the test, unlike the coverage shortfall the
same recipe's single-verdict addendum is about.

## Trail

- 2026-08-17: Landed at the [ADR-0002 rust-shuffle
  addendum](../../adr/ADR-0002-toolchain-gates.md), which also corrects the shuffle addendum's
  claim that libtest has no shuffle. Proved able to fail by a planted order-dependent pair with 58
  filler tests between its halves, passing 5 unshuffled runs of 5 and failing 5 of 5 at the frozen
  seed, with the real gate line exiting 101 and naming the test; the catch rate is 10 of 20 seeds,
  beside `scripts/`'s 11 of 20. It narrowed [R-288](288-nothing-schedules-the-shuffle-sweep.md)
  to the Python and overlay suites and opened nothing.
