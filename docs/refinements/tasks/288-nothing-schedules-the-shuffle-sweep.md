# Nothing schedules the shuffled test run

**Status:** done 2026-08-17
**Area:** repo-checks
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-checks.md)

Opened 2026-08-16 by the decision to shuffle under a fixed seed rather than a per-run one
([ADR-0002](../../adr/ADR-0002-toolchain-checks.md) decision 16). That decision rests on a measured
property of `pytest-randomly`: the order under a fixed seed is per item and stable, so a test added
today draws its position once against everything already there, and a pair that already coexists
under that order keeps the order it has forever. What that buys is a failure that always
reproduces. What it costs is that the pairs already in the tree are never redrawn.

`just shuffle [seed]` is where they get redrawn, and nothing ran it. It is deliberately not in
`just check`, since its whole point is an order nobody chose, and it was absent from CI for the
same reason. So it happened exactly when a person remembered it.

Closed by the first of the three shapes the entry costed, a scheduled workflow. The argument
against it was weaker than written: the recorded cost was "a failure that arrives detached from any
commit", which is a property of the defect rather than of the schedule, since the pair such a run
finds already coexisted and attaching the failure to the head commit would be false. The other two
shapes both put a lottery where a failure blocks work, once inside `just check` behind a cached
daily seed and once by raising the fixed constant, and the fixed-seed decision's reason for
refusing that has not changed. What remains is to put the lottery where a failure blocks nothing.

## History

- 2026-08-17: Narrowed to the two Python suites and the overlay by the pass that shuffled the Rust
  workspace ([R-287](287-rust-tests-run-in-one-fixed-order.md)). libtest seeds on the seed plus a
  hash of the binary's test-name list, so growing a Rust test binary redraws its whole permutation
  rather than inserting the new test into the existing order. The Rust tree therefore redraws every
  pair it has on every commit that adds a test to that binary.
- 2026-08-17: Done as `.github/workflows/shuffle.yml`
  ([ADR-0002](../../adr/ADR-0002-toolchain-checks.md) decision 18): a weekly cron plus a
  `workflow_dispatch` that takes a seed, both ending in `just shuffle "$SEED"`, so CI cannot
  diverge from what reproduces locally. It covers all four suites rather than the two the narrowing
  left open, since a Rust binary whose test list has stopped growing has one permutation exactly as
  pytest does, and since carving a CI-only variant out of a committed recipe is what the path-filter
  decision exists to prevent. Proved able to fail on the hard population rather than the easy one:
  the first planted pair fired at the fixed seed, so the ordinary check caught it and it proved
  nothing, and renaming the pair moved its per-item draw until `just check-scripts` reported `593
  passed` at 100% coverage over the defect while `just shuffle 5` exited 1 naming it. Catch rate 14
  of 40 seeds. It opened [R-291](291-a-red-sweep-leaves-no-trace-in-the-repo.md): a failing run
  whose only notification channel is one nothing in this repo can test.
