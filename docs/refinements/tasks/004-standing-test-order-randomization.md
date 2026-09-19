# Test-order randomization on every run

**Status:** done 2026-08-16
**Area:** repo-checks
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-checks.md)

Repair reports used to cite `-p no:randomly` as if it controlled test ordering. `pytest-randomly`
was a dependency of neither the brain workspace nor `scripts/`, so that flag suppressed a plugin
that was never loaded, and every suite had always run in collection order.

Three measurements followed, each supplying the plugin for the run only
(`uv run --with pytest-randomly pytest -p randomly --randomly-seed=N`) so no lockfile moved:

- 2026-07-18: three seeds over `packages/core` (990 tests) plus one over the whole brain workspace
  (1642 tests), all green, with `--collect-only` showing the order really differs between seeds.
- 2026-08-10: five seeds (1, 2, 3, 20260810, 987654321) over `brain/` (2306 tests, 65
  integration-marked deselected) and the same five over `scripts/` (400 tests). Ten runs, all
  green, all still at 100% line and branch coverage, since both `addopts` contain
  `--cov-fail-under=100`. Under seeds 2 and 3, `--collect-only` lists the same 2306 node ids with
  not one in the same position; under seeds 1 and 2 the `scripts/` suite lists the same 400 with 2
  in the same position. Neither failure kind appeared: a test failing because a sibling left state
  behind, or a test failing because the plugin reseeds `random` before each test. The second kind
  has no consumer here, since the only draw in the checked Python is `scripts/contrast.py:161`,
  whose bootstrap resampler uses its own `random.Random(seed)` instance, and the per-turn marker id
  in `cortex_core.untrusted` comes from `secrets.token_hex`.
- 2026-08-16: five seeds over `brain/` (2576 tests), five over `scripts/` (578) and five over the
  overlay's Vitest suite (57 files, 716 tests), which had never been shuffled. Fifteen runs, all
  green.

The first two passes recommended against adopting randomization, because a new order on every run
means recovering a seed from a log to reproduce a failure. The third pass changed that on a
property of the plugin the earlier ones assumed: a fixed seed does not redraw the order as the
suite grows. Adding a file left the other 578 `scripts/` node ids in the same relative order, and
growing a module from eight tests to nine inserted the ninth and left the eight where they were.
The order is per item and stable, so a fixed seed is not one order frozen forever: every new test
draws its own position once against everything already there, and a failure always reproduces.

Closed by adding `pytest-randomly` to both dev groups with a fixed `--randomly-seed` in each
`addopts`, `sequence: { shuffle: true, seed: N }` in `body/app/vite.config.ts`, and
`just shuffle [seed]` for a deliberate pass over the orders a fixed seed never draws. The cost is
real: on a planted order dependency, a fixed seed caught it at 11 of 20 seeds, and the first
planted pair did not fail at the chosen seed until its two tests were renamed. Two pieces are left
over: [R-287](287-rust-tests-run-in-one-fixed-order.md), the Rust suite this does not reach, and
[R-288](288-nothing-schedules-the-shuffle-sweep.md), the fact that nothing runs `just shuffle`.

## History

- 2026-07-18: Opened after a review found repair reports citing `-p no:randomly` when the plugin it
  names was installed by neither Python workspace.
- 2026-08-09: A review of triggers reached this entry by reading the tree, which cannot settle a
  trigger whose subject is what happens when the order changes.
- 2026-08-10: Measured again by running the suites rather than reading the tree, at a wider scope:
  ten shuffled runs over `brain/` and `scripts/`, all green at the 100% coverage both already
  require. Neither failure kind appeared, and adoption was recommended against. The run corrected
  the workspace figure of 1642 tests to 2306.
- 2026-08-16: Closed after a third measurement that added the overlay's Vitest suite and corrected
  2306 to 2576 and 400 to 578. Fifteen shuffled runs, all green. What changed the decision is that
  a fixed seed keeps its order stable as the suite grows, so it draws a position per new test
  rather than freezing one order. Randomization is now on in all three suites under a fixed seed,
  with `just shuffle` for the wider pass, checked with a planted dependency in `scripts/` and
  another in the overlay. It opened [R-287](287-rust-tests-run-in-one-fixed-order.md) and
  [R-288](288-nothing-schedules-the-shuffle-sweep.md).
