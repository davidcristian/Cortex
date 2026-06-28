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
   the gate exports JSON (`--json --summary-only`) and the script requires
   `data[0].totals.{lines,regions,branches}.percent == 100` (a metric with count 0 is
   vacuously satisfied, noted aloud).
3. **`scripts/` is a standalone uv project (`repo-gates`), not a brain workspace
   member.** Repo tooling is not brain domain code and must scan both trees; it is
   still gated exactly like all other Python (ruff, pyright strict, pytest at 100%).
4. **Generated-code marker: a directory named `_generated`.** The linecap scan skips
   any path containing a `_generated` component; coverage configs must exclude the same
   (implements ADR-0001 decision 7). No generated code exists yet; Slice 2 uses this.
5. **Tests live outside counted source files.** Rust tests go in `tests/` directories
   (never inline `#[cfg(test)]` modules, because the 300-line cap counts source files);
   Python tests in `tests/` directories. The linecap scan excludes `tests/` dir
   components plus `test_*.py`, `*_test.py`, `conftest.py`, `*_test.rs`.
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
