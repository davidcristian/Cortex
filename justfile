# `just check` is THE gate (AGENTS.md gate 6): CI and pre-commit run exactly these
# recipes. If it passes here, it passes there.

default: check

# All gates: cross-tree line cap first (fast), then the three tree checks in
# PARALLEL (ADR-0006), so wall time ≈ the slowest tree. Output is buffered per tree
# and printed in a fixed order so logs stay readable; any failure fails the gate.
# Kept bash-3.2 compatible (no `declare -A` etc.) for macOS system bash.
check:
    #!/usr/bin/env bash
    set -euo pipefail
    just check-linecap
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' EXIT
    echo "Running check-brain, check-scripts, check-body in parallel (output buffered)..."
    just check-brain >"$tmp/brain.log" 2>&1 &
    pid_brain=$!
    just check-scripts >"$tmp/scripts.log" 2>&1 &
    pid_scripts=$!
    just check-body >"$tmp/body.log" 2>&1 &
    pid_body=$!
    fail=0
    for tree in brain scripts body; do
        case "$tree" in
            brain) pid=$pid_brain ;;
            scripts) pid=$pid_scripts ;;
            body) pid=$pid_body ;;
        esac
        if wait "$pid"; then status=OK; else status=FAILED; fail=1; fi
        echo "=== check-$tree: $status ==="
        cat "$tmp/$tree.log"
    done
    exit "$fail"

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
    cd body && cargo clippy --locked --workspace --all-targets -- -D warnings
    cd body && cargo test --locked --workspace
    cd body && cargo +nightly llvm-cov --locked --branch --workspace --all-targets --ignore-filename-regex '/_generated/' --fail-under-lines 100 --fail-under-regions 100 --json --summary-only --output-path coverage.json
    cd scripts && uv sync --locked
    cd scripts && uv run python coverage_gate.py ../body/coverage.json

# Regenerate the committed seam stubs from proto/body.proto (needs local protoc; ADR-0003).
proto:
    mkdir -p /tmp/protostage/cortex_seam/_generated
    cp proto/body.proto /tmp/protostage/cortex_seam/_generated/
    cd brain && uv run python -m grpc_tools.protoc -I /tmp/protostage --python_out=packages/seam/src --grpc_python_out=packages/seam/src --pyi_out=packages/seam/src /tmp/protostage/cortex_seam/_generated/body.proto
    cd body && CORTEX_REGEN_PROTO=1 cargo build -p body-rpc

# Run the brain natively (no docker): BrainService on CORTEX_SEAM_HOST:CORTEX_SEAM_PORT.
brain-serve:
    cd brain && uv run python -m cortex_orchestrator

# Brain services in Compose (loopback-only publish; see docs/runbooks/local-dev-wsl.md).
up:
    docker compose up -d --build

down:
    docker compose down

# Brain + a GPU llama-server (real inference). Needs an NVIDIA GPU + configured models dir;
# see docs/runbooks/llamacpp-gpu.md. Never runs in CI (GPU-less by design, AGENTS.md gate 3).
up-gpu:
    docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build

down-gpu:
    docker compose -f docker-compose.yml -f docker-compose.gpu.yml down

# Live seam check from the body side. Needs a running brain (`just up` or `just brain-serve`);
# this is the Rust integration suite (#[ignore]-marked, never in CI/coverage per ADR-0003).
seam-health:
    cd body && cargo test -p body-rpc --test live -- --ignored --nocapture

# Live inference check: streams a real completion through LlamaCppBackend. Needs the gpu
# stack up (`just up-gpu`); integration-marked, never in CI/coverage (ADR-0007).
brain-inference-live:
    cd brain && CORTEX_INFERENCE_ENDPOINT=http://127.0.0.1:8080 uv run pytest -m integration --no-cov packages/inference
