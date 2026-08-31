# Nothing schedules the shuffle sweep

**Status:** landed 2026-08-17
**Area:** repo-gates
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-gates.md)

Opened 2026-08-16 by the decision to make the shuffle standing under a fixed seed rather than a
per-run one ([ADR-0002 shuffle addendum](../../adr/ADR-0002-toolchain-gates.md)). That decision
rests on a measured property of `pytest-randomly`: the order under a fixed seed is per item and
stable, so a test added today draws its position once against everything already there, and a pair
that already coexists under the frozen order keeps the order it has forever. What that buys is a
gate whose failure always reproduces. The half it costs is that the pairs already in the tree are
never re-drawn.

`just shuffle [seed]` is where they get re-drawn, and nothing ran it. It is not in `just check`
by design, since its whole point is an order nobody chose, and it was absent from CI for the same
reason. So the sweep happened exactly when a person remembered it, which is the same mechanism
this entry's own origin spent four weeks demonstrating the weakness of: the hand-run measurement
was re-derived three times by three passes that each had to read how the last one did it.

**What closed it.** The first of the three shapes the entry costed, a scheduled workflow, and the
argument against it turned out to be weaker than written. The recorded cost was "a red that arrives
detached from any commit", which is a property of the defect rather than of the schedule: the pair a
sweep finds already coexisted, so no commit introduced it and attaching the failure to the head
would be a fabrication. The other two shapes both put a lottery where a failure blocks work, once
inside `just check` behind a cached daily seed and once by bumping the frozen constant, and the
shuffle addendum's reason for refusing that has not changed. The remaining move is to put the
lottery where a failure blocks nothing, which is a workflow that gates nothing and is required by
nothing.

## Trail

- 2026-08-17: Narrowed to the two Python suites and the overlay by the pass that shuffled the Rust
  workspace ([R-287](287-rust-tests-run-in-one-fixed-order.md)). libtest seeds on the seed plus a
  hash of the binary's test-name list, so growing a Rust test binary re-draws its whole permutation
  rather than inserting the new test into the existing one. The Rust tree therefore re-draws every
  pair it holds on every commit that adds a test to that binary, which is what this entry needs a
  schedule to buy, and it needs no schedule to get it. Nothing about the Python and overlay half
  changes, `pytest-randomly`'s per-item stability being exactly the property this entry was opened
  about.
- 2026-08-17: Landed as `.github/workflows/shuffle.yml` at the [ADR-0002 sweep-schedule
  addendum](../../adr/ADR-0002-toolchain-gates.md): a weekly cron plus a `workflow_dispatch` that
  takes a seed, both ending in `just shuffle "$SEED"`, so CI cannot drift from what reproduces
  locally. It sweeps all four arms rather than the two the narrowing left open, since a Rust binary
  whose test list has stopped growing holds one permutation exactly as pytest does, and since
  carving a CI-only variant out of a committed recipe is the drift the path-filter ADR exists to
  prevent. Proved able to fail on the population this entry is about rather than the easy one: the
  first planted pair fired at the frozen seed, so the standing gate caught it and it proved nothing
  about a sweep, and renaming the pair moved its per-item draw until `just check-scripts` reported
  `593 passed` at 100% coverage over the defect while `just shuffle 5` exited 1 naming it. Catch
  rate 14 of 40 seeds. It opened [R-291](291-a-red-sweep-leaves-no-trace-in-the-repo.md), the red
  whose only push channel is a notification nothing in this repo can test.
