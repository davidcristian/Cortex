# ADR-0002: Toolchain and gate mechanics (Slice 1)

- **Status:** Accepted
- **Date:** 2026-06-28

## Context

Slice 1 turns AGENTS.md's hard gates into running machinery. Wiring them exposed
decisions the spec left open; this ADR records them so no future agent re-derives them.

## Decisions

1. **Rust branch coverage runs on nightly; everything else on stable.** LLVM branch
   instrumentation (`cargo llvm-cov --branch`) is nightly-only. All build/lint/test
   gates stay on stable; only the coverage step invokes `cargo +nightly llvm-cov`.
   In CI, nightly is installed before stable so stable remains the default toolchain.
2. **The Rust branch threshold is enforced by `scripts/coverage_gate.py`.**
   cargo-llvm-cov has `--fail-under-lines/-regions` but no `--fail-under-branches`, so
   the gate exports JSON (`--json --summary-only`) and the script requires exactly one
   `data[]` entry and `covered == count` for each of
   `data[0].totals.{lines,regions,branches}`. The producer's `percent` is never
   trusted (a metric with count 0 is vacuously satisfied, noted aloud).
3. **`scripts/` is a standalone uv project (`repo-gates`), not a brain workspace
   member.** Repo tooling is not brain domain code and must scan both trees; it is
   still gated exactly like all other Python (ruff, pyright strict, pytest at 100%).
4. **Generated-code marker: a directory named `_generated`.** The linecap scan skips
   any path containing a `_generated` component; coverage configs must exclude the same
   (implements ADR-0001 decision 7). No generated code exists yet; Slice 2 uses this.
5. **Tests live outside counted source files.** Rust tests go in `tests/` directories;
   Python tests in `tests/` directories. The linecap scan excludes `tests/` dir
   components plus `test_*.py`, `*_test.py`, `conftest.py`, `*_test.rs`.
   *Amended (2026-08-03):* the scan reaches the overlay's TypeScript too, so both lists
   grew, this one by Vitest's own `*.test.ts`/`*.test.tsx` plus `test-setup.ts`, and
   decision 4's by `dist` and `coverage`. The suffixes, the skips and what stays outside
   the cap are decided in the [ADR-0011](ADR-0011-body-v1.md) line-cap addendum.
   *Amended (Slice 2):* a narrowly-scoped inline `#[cfg(test)]` module is permitted
   when it unit-tests private internals unreachable through the public API (first use:
   the status-mapping helpers in `body/crates/rpc/src/client.rs`). Inline tests count
   toward the file's 300-line cap, which keeps them small; prefer `tests/` whenever
   the behavior is publicly reachable.
6. **Ruff runs with `select = ["ALL"]`** and a short, individually-justified ignore
   list in the root `ruff.toml`, shared by every Python project in the repo.
7. **Rust policy details:** edition 2024; `unsafe_code = "forbid"` and clippy
   `unwrap_used`/`expect_used = "deny"` via workspace lints (relaxed in tests through
   `clippy.toml`); clippy pedantic on at warn (escalated by `-D warnings`). A future OS
   adapter crate that genuinely needs `unsafe` gets its own ADR plus a scoped lint
   override, per AGENTS.md gate 5.
8. **Python policy details:** CPython 3.12 baseline; pyright strict; the `integration`
   pytest marker is excluded via addopts (`-m "not integration"`) so live suites never
   count toward or run under the coverage gate.
9. **pre-commit is a single local hook running `just check`** (a literal mirror), so
   the hook can never drift from the gate.

## Consequences

- A second toolchain (nightly) must be present for coverage runs; `rustup toolchain
  install nightly --component llvm-tools-preview` is part of machine setup.
- The coverage gate's JSON parsing couples loosely to cargo-llvm-cov's export format;
  the schema check fails loudly (typed errors) if the format shifts.
- `select = ["ALL"]` means new ruff releases can introduce new failures; fixing or
  narrowly ignoring them (with a reason) is part of routine maintenance.

## Addendum (2026-07-18): test-order randomization is not installed, so it is not a gate

A review of the brain-handoff work found several repair reports citing `-p no:randomly` on the
commands they ran, as evidence that ordering had been controlled for. It is not evidence of
anything here: `pytest-randomly` is **not** a dependency of the brain workspace (nor of
`scripts/`), so `-p no:randomly` disables a plugin that was never loaded and every suite has
always run in collection order. A flag naming an absent plugin reads exactly like a gate that
cannot fail, which is why this is written down rather than quietly dropped.

**What was done instead of citing it.** The plugin was supplied for the run only, with
`uv run --with pytest-randomly pytest -p randomly --randomly-seed=N`, and the suites were
actually shuffled: three seeds over `packages/core` (990 tests each) and one over the whole brain
workspace (1642 tests), all green, with `--collect-only` confirming the collected order really
differs between seeds, so the shuffle was doing something. That is the measurement the
determinism claim now rests on, and the chaos suite's own docstring says so.

**Why it is not being added to `just check`.** Making it standing would change what the gate
does on every run: the order becomes different each invocation, so a failure is reproducible only
by reading the seed out of the log, and the plugin also reseeds `random` per test, which is a
behaviour change for any test that draws. Both are defensible, but they are a gate-policy
decision with a real cost at personal scale, and the measured shuffles above found nothing for
them to catch. Recorded as a fix-when-it-bites deferral in
[docs/refinements/repo-gates.md](../refinements/repo-gates.md) with its trigger: a test that
passes alone and fails in a suite, or any order-dependent flake.
