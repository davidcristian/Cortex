# `just check` is THE gate (AGENTS.md gate 6): CI and pre-commit run exactly these
# recipes. If it passes here, it passes there.

default: check

# All gates: cross-tree line cap, both Python projects, the Rust workspace.
check: check-linecap check-brain check-scripts check-body

# AGENTS.md gate 1: ≤300 lines per non-test .py/.rs source file, both trees.
check-linecap:
    cd scripts && uv sync --locked
    cd scripts && uv run python linecap.py --root ..

# Python brain workspace: format, lint, strict types, tests at 100% line+branch.
check-brain:
    cd brain && uv sync --locked
    cd brain && uv run ruff format --check .
    cd brain && uv run ruff check .
    cd brain && uv run pyright
    cd brain && uv run pytest

# Repo gate tooling: gated exactly like any other Python in the repo.
check-scripts:
    cd scripts && uv sync --locked
    cd scripts && uv run ruff format --check .
    cd scripts && uv run ruff check .
    cd scripts && uv run pyright
    cd scripts && uv run pytest

# Rust body workspace: fmt, clippy -D warnings, tests, then coverage at 100%
# line+region+branch. Branch instrumentation needs nightly, and cargo-llvm-cov has no
# --fail-under-branches, so the JSON export is checked by coverage_gate.py (ADR-0002).
check-body:
    cd body && cargo fmt --all --check
    cd body && cargo clippy --workspace --all-targets -- -D warnings
    cd body && cargo test --workspace
    cd body && cargo +nightly llvm-cov --branch --workspace --all-targets --fail-under-lines 100 --fail-under-regions 100 --json --summary-only --output-path coverage.json
    cd scripts && uv sync --locked
    cd scripts && uv run python coverage_gate.py ../body/coverage.json
