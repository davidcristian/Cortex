# Standing test-order randomization

**Status:** landed 2026-08-16
**Area:** repo-gates
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-gates.md)

Opened 2026-07-18, fix-when-it-bites, by a review that
found repair reports citing `-p no:randomly` as if it controlled for ordering. `pytest-randomly`
is not a dependency of the brain workspace or of `scripts/`, so that flag suppresses a plugin
that was never loaded and every suite has always run in collection order; the citation was a
gate that could not fail. What replaced it is a real measurement rather than a standing gate:
the plugin supplied for the run only (`uv run --with pytest-randomly pytest -p randomly
--randomly-seed=N`), three seeds over `packages/core` (990 tests) plus one over the whole brain
workspace (1642 tests), all green, with `--collect-only` proving the order genuinely differs
between seeds. Making it standing is a gate-policy change with real cost: every run would use a
different order, so reproducing a failure means recovering the seed from the log, and the plugin
reseeds `random` per test, which changes behaviour for any test that draws. **Trigger:** a test
that passes alone and fails inside a suite, or any order-dependent flake; the fix is then adding
`pytest-randomly` to the brain (and `scripts/`) dev dependencies with the seed printed by the
header it already emits. The `just check` recipes are unchanged for now
([ADR-0002 addendum](../../adr/ADR-0002-toolchain-gates.md)).

**Run rather than read on 2026-08-10, at a wider scope, and the trigger did not fire.** The
fix-when-it-bites sweep of 2026-08-09 recorded on [index.md](../index.md) reached this entry by
reading the tree, which cannot settle a trigger whose whole subject is what happens when the
order changes, so the measurement was repeated rather than the verdict carried forward. Same
recipe, the plugin supplied for the run only so neither lockfile moved:
`uv run --with pytest-randomly pytest -p randomly --randomly-seed=N`, from `brain/` at seeds 1,
2, 3, 20260810 and 987654321 (2306 tests each, 65 integration-marked deselected) and from
`scripts/` at the same five seeds (400 tests each). Ten runs, every one green, and every one
still reporting 100% line and branch coverage, which is asserted rather than eyeballed because
both `addopts` carry `--cov-fail-under=100` and a randomized run inherits it. The scope is wider
than the check recorded above in two ways: the whole brain workspace at every seed rather than
`packages/core` at three seeds and the workspace once, and the `scripts/` suite, which had never
been shuffled at all. That workspace has also grown from the 1642 tests this entry records to
2306, which is the other reason not to carry an old verdict forward. The shuffle moved the order,
proven the same way it was the first time: `--collect-only` under seeds 2 and 3 lists
the same 2306 node ids with **not one** in the same position, and under seeds 1 and 2 the
`scripts/` suite lists the same 400 with 2 in the same position.

**The two failure kinds were separated before the runs, and neither appeared.** A test that
fails because a sibling left state behind is the order dependency this entry waits for; a test
that fails because the plugin reseeds `random` before each test is a property of the plugin,
which this entry already predicts and which would say nothing about the suite. Nothing failed,
so neither is in the tree today, and the second kind turns out to have no reachable consumer in
either suite: the only draw in the whole of the gated Python is `scripts/contrast.py:161`, whose
bootstrap resampler is a `random.Random(seed)` instance of its own rather than the module global
the plugin reseeds (its tests pass the seed explicitly and assert the interval is a function of
it), and the one place that needs unpredictability, the per-turn marker id in
`cortex_core.untrusted`, draws from `secrets.token_hex`, which no seed reaches. So the cost this
entry weighs against adoption is really its first half alone, a different order every run and a
seed to recover from the log.

**Adoption stays the maintainer's call and is recommended against for now**, recorded here
rather than taken, since a gate change is not a measurement's to make. Ten shuffled runs over
two suites found nothing to catch, so a standing gate would buy protection against an order
dependency nobody has introduced yet at the price of a gate whose failures are not reproducible
without reading a seed out of a log. The honest middle option, if it ever looks worth it, is a
fixed `--randomly-seed` in `addopts`, which buys one deterministic order that is not the
collection order rather than a new one per run; it would have found nothing here either. The
trigger is unchanged and the entry stays open
([ADR-0002 addendum on re-running the shuffle](../../adr/ADR-0002-toolchain-gates.md)).

**Closed 2026-08-16, the third measurement having found the thing the first two assumed**
([ADR-0002 shuffle addendum](../../adr/ADR-0002-toolchain-gates.md)). The runs were repeated a
third time rather than read, wider again: five seeds over `brain/` (2576 tests, both figures above
now stale), five over `scripts/` (578) and five over the overlay's Vitest suite, which had never
been shuffled at all (57 files, 716 tests). Fifteen runs, every one green, so the trigger has now
failed to fire three times.

The verdict changed anyway, on a property of the plugin neither earlier pass measured. **A fixed
seed does not re-draw as the suite grows**, which both earlier passes assumed it would and which
turns out to be the opposite of true: adding a file left the other 578 `scripts/` node ids in the
same relative order, and growing an isolated module from eight tests to nine inserted the ninth and
left the eight in theirs. The order is per item and stable. So the middle option those passes named
and dismissed is not a single order frozen forever: it is an order in which every new test draws
its own position once, against everything already there, which is exactly the moment this entry's
trigger describes, and its failures always reproduce. That is what landed:
`pytest-randomly` in both dev groups with a fixed `--randomly-seed` in each `addopts`, `sequence:
{ shuffle: true, seed: N }` in `body/app/vite.config.ts`, and `just shuffle [seed]` for the
deliberate sweep over the orders a fixed seed never draws.

The cost this entry weighed is paid rather than avoided: the standing draw is about even per pair,
measured at 11 of 20 seeds on a planted dependency, and the first plant written did not fire at the
frozen seed until its two tests were renamed. What is left over is written down as
[R-287](287-rust-tests-run-in-one-fixed-order.md), the Rust suite that this decision does not
reach, and [R-288](288-nothing-schedules-the-shuffle-sweep.md), the sweep that nothing runs.

## Trail

- 2026-07-18: Opened as fix-when-it-bites by a review that found repair reports citing `-p
  no:randomly` as if it controlled for ordering, when the plugin it names is installed by neither
  Python workspace, so the citation was a gate that could not fail. The index names the review
  more precisely than the entry does: a verification pass over the brain-handoff conductor that
  found no new correctness defect but two deferrals nobody had written down, which under the
  doc-first Definition of Done is itself the violation, and it calls this the rarer kind of
  finding, not a defect in the code but in what was claimed about it.
- 2026-08-09: The fix-when-it-bites trigger sweep reached this entry by reading the tree, which
  the index records as unable to settle a trigger whose whole subject is what happens when the
  order changes.
- 2026-08-10: Re-derived by running the check rather than reading the tree, at a wider scope. Ten
  shuffled runs with the plugin supplied for the run only, five seeds over the whole brain
  workspace (2306 tests, 65 integration-marked deselected) and five over `scripts/` (400 tests),
  are all green at the 100% coverage both suites already demand, with `--collect-only` proving the
  order genuinely moved. Neither failure kind appeared, the trigger did not fire, and adoption is
  recommended against and left to the maintainer. The run corrected the entry's own workspace
  figure of 1642 tests to 2306.
- 2026-08-16: closed by measuring a third time, adding the overlay's Vitest suite to the scope and
  correcting 2306 to 2576 and 400 to 578. Fifteen shuffled runs, all green, so the trigger has
  still never fired; what changed the verdict is that a fixed seed was measured to keep its order
  stable as the suite grows, which makes it a draw per new test rather than the frozen order both
  earlier passes took it for. The shuffle is standing under a fixed seed in all three suites, with
  `just shuffle` for the sweep, proved able to fail by a planted pair in `scripts/` and another in
  the overlay. It opened [R-287](287-rust-tests-run-in-one-fixed-order.md) and
  [R-288](288-nothing-schedules-the-shuffle-sweep.md).
