# ADR-0006: Gate performance via path-filtered CI and a parallel local gate

- **Status:** Accepted
- **Date:** 2026-06-29

## Context

Measured on the dev machine after Slice 3: the full warm gate is ~15 s (brain 7 s,
body 6 s, scripts 2 s, linecap 0.2 s) and an incremental Rust change re-gates in ~4 s.
The real costs were elsewhere: a hook bug ran the entire gate twice per commit (fixed
as a defect, `a51ce2d`), and cold builds, where CI compiles the Rust dependency tree three
times (clippy/test/coverage profiles) on a fresh 2-core runner regardless of what
changed, and every push queued a full run even when a newer push had superseded it.

## Decisions

1. **CI is path-filtered** (dorny/paths-filter, a `changes` job feeding job-level
   `if`s): the python job runs for `brain/**`, `ruff.toml`, or shared files; the rust
   job for `body/**` or shared files; **shared** = `justfile`,
   `.github/workflows/ci.yml`, `proto/**`, `scripts/**`, `.python-version`, all the files
   that can affect both toolchains' gates. Docs-only pushes skip both jobs (the run is
   still green). AGENTS.md gate 3 is amended accordingly: CI builds each toolchain
   when a change can affect it.
2. **CI runs are superseded per ref**: `concurrency` with `cancel-in-progress`, so a
   newer push cancels the in-flight run for the same branch.
3. **`just check` parallelizes the tree checks**: linecap runs first (fast,
   fail-early), then check-brain / check-scripts / check-body run concurrently with
   per-tree buffered output printed in fixed order. Wall time ≈ the slowest tree.
   Concurrent `uv sync` on the scripts venv (check-scripts vs. check-body's gate step)
   is safe, because uv serializes per-environment via its own lock.

## Consequences

- The shared-filter list is now load-bearing: a new cross-tree file (e.g. a future
  shared config) must be added to it, or CI can green-light a change it never tested.
  Review the list whenever repo structure changes.
- Skipped CI jobs report "skipped", not "passed", which is expected and fine for this repo.
- Buffered parallel gate output means no live streaming per tree; logs print complete,
  per tree, on completion.
- Observed adjacent gap while writing the filters (not addressed here): nothing in CI
  verifies the committed `_generated` stubs are fresh against `proto/body.proto`; a
  stub-freshness check would close it (candidate for the next seam-touching slice).
