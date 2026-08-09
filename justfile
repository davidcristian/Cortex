# `just check` is THE gate (AGENTS.md gate 6): CI and pre-commit run exactly these
# recipes. If it passes here, it passes there.

default: check

# All gates: the four cross-tree scans first (fast), then the four tree checks in
# PARALLEL (ADR-0006), so wall time ≈ the slowest tree. Output is buffered per tree
# and printed in a fixed order so logs stay readable; any failure fails the gate.
# Kept bash-3.2 compatible (no `declare -A` etc.) for macOS system bash.
check:
    #!/usr/bin/env bash
    set -euo pipefail
    just check-linecap
    just check-dashcheck
    just check-crosscheck
    just check-bindcheck
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' EXIT
    echo "Running check-brain, check-scripts, check-body, check-overlay in parallel (buffered)..."
    just check-brain >"$tmp/brain.log" 2>&1 &
    pid_brain=$!
    just check-scripts >"$tmp/scripts.log" 2>&1 &
    pid_scripts=$!
    just check-body >"$tmp/body.log" 2>&1 &
    pid_body=$!
    just check-overlay >"$tmp/overlay.log" 2>&1 &
    pid_overlay=$!
    fail=0
    for tree in brain scripts body overlay; do
        case "$tree" in
            brain) pid=$pid_brain ;;
            scripts) pid=$pid_scripts ;;
            body) pid=$pid_body ;;
            overlay) pid=$pid_overlay ;;
        esac
        if wait "$pid"; then status=OK; else status=FAILED; fail=1; fi
        echo "=== check-$tree: $status ==="
        cat "$tmp/$tree.log"
    done
    exit "$fail"

# AGENTS.md gate 1: ≤300 lines per non-test .py/.rs/.ts/.tsx source file, every tree.
check-linecap:
    cd scripts && uv sync --locked
    cd scripts && uv run python linecap.py --root ..

# No dash as punctuation, in any text file across every tree.
check-dashcheck:
    cd scripts && uv sync --locked
    cd scripts && uv run python dashcheck.py --root ..

# One value, declared once per language: every registered constant still agrees with itself.
check-crosscheck:
    cd scripts && uv sync --locked
    cd scripts && uv run python crosscheck.py --root ..

# No compose bind default lands a container-written path in the tree that git does not ignore.
check-bindcheck:
    cd scripts && uv sync --locked
    cd scripts && uv run python bindcheck.py --root ..

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
# Two ungated trees the workspace gate would otherwise miss are folded in here (ADR-0011):
# the excluded Tauri shell (body/app/src-tauri) gets its own fmt --check (parse only, no
# build, no extra dep), and the cfg(windows) os_windows backend gets a clippy on the
# windows target, since the native --workspace clippy compiles that crate to nothing on
# Linux. os_windows fmt is already caught by `cargo fmt --all` above (it is a workspace
# member and rustfmt ignores cfg). The windows target must be installed (rustup target add
# x86_64-pc-windows-msvc); clippy never links, so no MSVC toolchain is needed. Shell clippy
# stays out (it needs the Linux GTK/webkit/dbus dev packages), recorded in docs/refinements.
check-body:
    cd body && cargo fmt --all --check
    cd body/app/src-tauri && cargo fmt --check
    cd body && cargo clippy --locked --workspace --all-targets -- -D warnings
    cd body && cargo clippy --locked --target x86_64-pc-windows-msvc -p os-windows --all-targets -- -D warnings
    cd body && cargo test --locked --workspace
    cd body && cargo +nightly llvm-cov --locked --branch --workspace --all-targets --ignore-filename-regex '/_generated/' --fail-under-lines 100 --fail-under-regions 100 --json --summary-only --output-path coverage.json
    cd scripts && uv sync --locked
    cd scripts && uv run python coverage_gate.py ../body/coverage.json

# Overlay frontend (React + Vite): typecheck + Vitest at 100% line+branch coverage
# (ADR-0011 addendum). Host-only node toolchain, path-filtered in CI (ADR-0006); its .ts/.tsx
# is under the line cap since the ADR-0011 line-cap addendum, scanned by check-linecap above.
# Entry glue (main.tsx), the real Tauri bridge, and the browser-dev demo are coverage-excluded.
check-overlay:
    cd body/app && npm ci
    cd body/app && npm run typecheck
    cd body/app && npm run test:cov

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
# Compose files live under docker/; `--project-directory .` keeps ./brain, ./sandbox, the .env,
# and the `cortex` project name resolving from the repo root (see docker/docker-compose.yml).
up:
    docker compose --project-directory . -f docker/docker-compose.yml up -d --build

down:
    docker compose --project-directory . -f docker/docker-compose.yml down

# Brain + a GPU llama-server (real inference). Needs an NVIDIA GPU + configured models dir;
# see docs/runbooks/llamacpp-gpu.md. Never runs in CI (GPU-less by design, AGENTS.md gate 3).
up-gpu:
    docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.gpu.yml up -d --build

down-gpu:
    docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.gpu.yml down

# Live seam check from the body side. Needs a running brain (`just up` or `just brain-serve`);
# this is the Rust integration suite (#[ignore]-marked, never in CI/coverage per ADR-0003).
seam-health:
    cd body && cargo test -p body-rpc --test live -- --ignored --nocapture

# Live inference check: streams a real completion through LlamaCppBackend. Needs the gpu
# stack up (`just up-gpu`); integration-marked, never in CI/coverage (ADR-0007).
brain-inference-live:
    cd brain && CORTEX_INFERENCE_ENDPOINT=http://127.0.0.1:8080 uv run pytest -m integration --no-cov packages/inference

# The end-to-end turn-cost measurement (ADR-0038 harness addendum): three blocks in A/B/A order,
# each a brain container recreated with one environment variable changed, then the blocked paired
# bootstrap over the three samples. THE RESTARTS LIVE HERE rather than in the test because an arm
# is a container configuration, so changing one is a deployment step; the test measures one block
# and `scripts/contrast.py` reads the blocks back. The outer two blocks are the control: same
# configuration, different times, so their contrast is the run-to-run noise floor the middle block
# has to clear, and a null interval that does not span zero says the run drifted.
# Needs a real GPU, the models dir, and roughly 15 minutes at the default size; never runs in CI.
# Reproduces docs/adr/ADR-0038-ranked-recall.md; runbook: docs/runbooks/memory-pgvector.md.
turn-cost arm="judge" control="raw" reps="8":
    #!/usr/bin/env bash
    set -euo pipefail
    compose="docker compose --project-directory . -f docker/docker-compose.yml"
    compose="$compose -f docker/docker-compose.gpu.yml -f docker/docker-compose.memory.yml"
    mkdir -p measurements
    # Every other failure in this measurement is loud, so the one wait is bounded too: a brain
    # that never reaches healthy (bad env, a model the host cannot mount, a failed migration)
    # would otherwise hang here forever, and `set -e` cannot see a loop that never exits. The
    # healthcheck first probes at 15s and gives up after 3 retries at 30s, so this is past any
    # honest slow start and short of a wait an operator would sit through twice.
    health_wait=180
    $compose up -d --build
    run_block () {
        echo "=== block $1: recall=$2 ==="
        CORTEX_MEMORY_RECALL="$2" CORTEX_MEMORY_SCOPE=session CORTEX_MEMORY_RECALL_AUDIT=1 \
            $compose up -d --no-deps --force-recreate brain
        deadline=$((SECONDS + health_wait))
        until $compose ps brain | grep -q '(healthy)'; do
            if [ "$SECONDS" -ge "$deadline" ]; then
                echo "block $1 (recall=$2): brain never reported (healthy) in ${health_wait}s" >&2
                $compose ps brain >&2
                echo "diagnose with: $compose logs brain" >&2
                exit 1
            fi
            sleep 1
        done
        cd brain && CORTEX_TURN_COST_ARM="$2" CORTEX_TURN_COST_REPS="{{ reps }}" \
            CORTEX_TURN_COST_OUT="../measurements/block-$1-$2.json" \
            uv run pytest -m integration --no-cov -s \
            packages/orchestrator/tests/test_turn_cost_live.py
        cd ..
    }
    run_block 1 "{{ control }}"
    run_block 2 "{{ arm }}"
    run_block 3 "{{ control }}"
    cd scripts && uv sync --locked
    uv run python contrast.py "../measurements/block-1-{{ control }}.json" \
        "../measurements/block-2-{{ arm }}.json" "../measurements/block-3-{{ control }}.json"

# The gpu stack PLUS a loopback publish of the model-host control API, which the base gpu override
# deliberately withholds (it can start and stop GPU processes, ADR-0030 d3). For live tests only;
# `just down-gpu` takes it down. Procedure: docs/runbooks/model-swap.md.
up-modelhost-loopback:
    docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.gpu.yml -f docker/docker-compose.modelhost-loopback.yml up -d --build

# Live model-host check: starts, health-gates and stops a real llama-server through the real
# ModelHost adapter. Needs `just up-modelhost-loopback`; integration-marked, never in CI/coverage.
brain-modelhost-live:
    cd brain && CORTEX_MODELHOST_ENDPOINT=http://127.0.0.1:9300 uv run pytest -m integration --no-cov packages/model_manager
