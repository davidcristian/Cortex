# scripts/ (`repo-gates`)

**Purpose.** The repo's own gate tooling: the cross-tree line cap and the Rust branch
coverage threshold. A standalone uv project (not a brain workspace member, per ADR-0002),
gated exactly like all other Python.

**Public contract** (both are CLIs invoked by `just` recipes; both also expose a pure,
unit-tested core function).

- `linecap.py [--root DIR] [--max-lines N]` implements AGENTS.md gate 1. Scans `*.py`/`*.rs`
  under `--root` (default `.`), counting ALL lines (code, comments, blanks; cap default
  300). Skips dir components `.git`, `.venv`, `target`, `node_modules`, `__pycache__`,
  `.pytest_cache`, `.ruff_cache`, `tests`, `_generated` (the generated-code marker),
  and test-named files (`test_*.py`, `*_test.py`, `conftest.py`, `*_test.rs`).
  Exit 0 with a summary line; exit 1 printing `path: N lines (cap M)` per violation;
  exit 2 if `--root` is not a directory.
- `coverage_gate.py PATH` reads a `cargo llvm-cov --json --summary-only` export and
  requires `data[0].totals.{lines,regions,branches}.percent == 100`. A metric with
  `count == 0` passes vacuously (with a printed note). Malformed/missing input → typed
  error, exit 1. Exit 0 only when all three metrics pass.

**Invariants.**
- stdlib-only modules; pure cores (`scan`, `evaluate`/`check`) unit-tested to 100%
  line+branch; the only coverage pragmas are the two `__main__` guard lines.
- The exclusion lists above are the single definition of "non-test source file" and
  "generated code" for the cap. Change them only with an ADR update.

**Dependencies.** Python stdlib; dev-only: pytest, pytest-cov, pyright, ruff.
