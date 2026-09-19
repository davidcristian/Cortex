# Runbook: reproducing a shuffled test failure

Every suite in `just check` runs in a shuffled order under a fixed seed, so a red run reproduces
exactly and a test that depends on a sibling is found rather than tolerated. This is how to
reproduce one, and what `just shuffle` adds. Setting the toolchains up:
[local-dev-wsl.md](local-dev-wsl.md). Decision:
[ADR-0002](../adr/ADR-0002-toolchain-checks.md).

## The seeds

Every suite in `just check` runs in a shuffled order under a fixed seed: `--randomly-seed=9973` in
`brain/pyproject.toml`, `7919` in `scripts/pyproject.toml`,
`sequence: { shuffle: true, seed: 65537 }` in `body/app/vite.config.ts`, and
`-- -Z unstable-options --shuffle-seed=104729` on `check-body`'s coverage step in the `justfile`.
So the order is not the collection order and is still the same order twice: a red run reproduces
exactly, here and in CI, and pytest prints `Using --randomly-seed=N` in its header. Reproducing a
failure in isolation needs that seed, `uv run pytest --randomly-seed=9973 <path>`, or the test
runs in a different order than the failing run did. Never tune a seed to make a test pass; that
throws away every draw the suite has survived and hides the dependency rather than fixing it.

The Rust half has different mechanics. It runs on the nightly coverage step, because libtest's
shuffle is nightly-only behind `-Z unstable-options` and every other Rust check stays on stable,
so `just check` runs that suite twice, alphabetically and permuted, and both must pass. Each test
binary prints `running N tests (shuffle seed: 104729)`. Reproducing one binary in isolation is
`cargo +nightly test -p body-rpc --test body_server -- -Z unstable-options --shuffle-seed=104729`,
and adding `--test-threads=1` is what makes the order readable, since libtest permutes dispatch
into parallel threads rather than running serially. Unlike pytest, adding one test redraws its
whole binary, so a red there can name a pair you did not touch.

`just shuffle [seed]` is the one thing `just check` does not do: all four suites at one seed of
your choosing, a random one by default, printed so the run reproduces with `just shuffle <seed>`.
Run it when a test behaves as though a sibling left something behind, and after adding a batch of
tests. It stays out of `just check` because its point is an order nobody chose, and a pre-commit
check cannot absorb a red the committer cannot reproduce.

`.github/workflows/shuffle.yml` draws a seed every Monday and takes one from the Actions tab on
demand, so that the pairs the fixed seeds never draw get drawn without anyone remembering.
**Neither it nor `ci.yml` has ever run**, because GitHub Actions is turned off for this repository
by the maintainer's choice; `gh api repos/<owner>/<repo>/actions/workflows/shuffle.yml/runs`
reports the workflow's `total_count`, which says whether that has changed. It blocks no merge and
no push, so read a red there as a real order dependency between two tests that already coexisted
rather than as a fault in whatever commit was at the head; the run's summary names the seed and the
`just shuffle <seed>` that replays it locally. GitHub disables a schedule on a public repository
after 60 days of no activity.

