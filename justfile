# `just check` is THE gate (AGENTS.md gate 6): CI and pre-commit run exactly these
# recipes. If it passes here, it passes there.

default: check

# All gates: the five cross-tree scans first (fast), then the four tree checks in
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
    just check-backlog
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

# Each backlog index still matches the task files it describes (ADR-0039). A task's
# status lives on its own Status line and nowhere else, so this is the only thing
# holding the generated index to it. It also holds every pointer at one of those
# indexes, path and anchor both, so a renamed area cannot leave a resolving link on a
# heading nobody renders. Regenerate with `just backlog`.
check-backlog:
    cd scripts && uv sync --locked
    cd scripts && uv run python backlogcheck.py --root ..

# Rewrite each backlog index from its task files. Run after closing or filing a task.
backlog:
    cd scripts && uv sync --locked
    cd scripts && uv run python backlogcheck.py --root .. --write

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
# line+region+branch. Branch instrumentation needs nightly, and ALL THREE thresholds are
# coverage_gate.py's, reading the JSON export (ADR-0002). cargo-llvm-cov's own
# --fail-under-lines/-regions used to sit here too, and came off: with the report diverted by
# --json --output-path they exit 1 printing nothing at all, so the one failure this has ever
# had said only that a recipe line failed, and the gate that names the metric and the
# percentage never ran (ADR-0002 single-verdict addendum).
# Two ungated trees the workspace gate would otherwise miss are folded in here (ADR-0011):
# the excluded Tauri shell (body/app/src-tauri) gets its own fmt --check (parse only, no
# build, no extra dep), and the cfg(windows) os_windows backend gets a clippy on the
# windows target, since the native --workspace clippy compiles that crate to nothing on
# Linux. os_windows fmt is already caught by `cargo fmt --all` above (it is a workspace
# member and rustfmt ignores cfg). The windows target must be installed (rustup target add
# x86_64-pc-windows-msvc); clippy never links, so no MSVC toolchain is needed. Shell clippy
# stays out (it needs the Linux GTK/webkit/dbus dev packages), recorded in docs/refinements.
# The coverage run also excludes Cargo build scripts (`build.rs`), which rustc began
# instrumenting during the 1.99 nightlies: a build script runs at build time, not under the
# test harness, so no test can reach it (ADR-0002 build-script addendum).
# The step names the two versions it is about to measure with BEFORE it measures, because
# `+nightly` is a channel and cargo-llvm-cov installs unversioned on both sides, so CI and this
# machine routinely resolve different ones. A coverage failure then carries its own toolchain in
# the log, which is what tells a toolchain change from the commit under test without a local
# bisect against two nightlies (ADR-0002 toolchain-print addendum). CI runs this same recipe, so
# both sides print, and a machine missing nightly now fails here rather than mid-measurement.
# Both probes are then handed to the gate, which reads rather than echoes them: it prints the
# compiler beside its verdict, and refuses an export whose own recorded writer is not the
# cargo-llvm-cov that just ran. They are probed twice on purpose, once as a standing line so a
# missing nightly fails before the measurement and once here, which costs milliseconds and
# spares the recipe a temp file to carry a string between two shells.
# THE SHUFFLE RIDES THE COVERAGE STEP, not the `cargo test` above it (ADR-0002 rust-shuffle
# addendum). libtest does have a shuffle, but only on nightly behind `-Z unstable-options`, and
# ADR-0002 decision 1 keeps every build/lint/test gate on stable. This step is already nightly and
# already runs the whole workspace, so the gate gets BOTH orders per run at no extra wall time: the
# stable run in libtest's alphabetical order, this one permuted. The seed is FIXED so a red
# reproduces, and each test binary prints `(shuffle seed: 104729)` in its header, so a failing log
# names the order it ran in. Unlike a coverage shortfall, a test failure here is loud and names the
# test. `just shuffle` is the sweep over the orders this one seed never draws.
check-body:
    cd body && cargo fmt --all --check
    cd body/app/src-tauri && cargo fmt --check
    cd body && cargo clippy --locked --workspace --all-targets -- -D warnings
    cd body && cargo clippy --locked --target x86_64-pc-windows-msvc -p os-windows --all-targets -- -D warnings
    cd body && cargo test --locked --workspace
    cd body && rustc +nightly --version
    cd body && cargo +nightly llvm-cov --version
    cd body && cargo +nightly llvm-cov --locked --branch --workspace --all-targets --ignore-filename-regex '/_generated/|/build[.]rs$' --json --summary-only --output-path coverage.json -- -Z unstable-options --shuffle-seed=104729
    cd scripts && uv sync --locked
    cd scripts && uv run python coverage_gate.py ../body/coverage.json --rustc "$(rustc +nightly --version)" --llvm-cov "$(cargo +nightly llvm-cov --version)"

# Overlay frontend (React + Vite): typecheck + Vitest at 100% line+branch coverage
# (ADR-0011 addendum). Host-only node toolchain, path-filtered in CI (ADR-0006); its .ts/.tsx
# is under the line cap since the ADR-0011 line-cap addendum, scanned by check-linecap above.
# Entry glue (main.tsx), the real Tauri bridge, and the browser-dev demo are coverage-excluded.
check-overlay:
    cd body/app && npm ci
    cd body/app && npm run typecheck
    cd body/app && npm run test:cov

# The deliberate shuffle sweep, which `just check` is deliberately not (ADR-0002 shuffle
# addendum). Each gated suite runs its tests in a shuffled order under a FIXED seed, so the
# gate is reproducible and draws one order per test rather than a fresh lottery per run. This
# recipe is where the other orders get drawn: it runs all four suites at ONE seed of your
# choosing, defaulting to a random one, and prints it. A failure here reproduces with
# `just shuffle <seed>`, and a suite reproduces alone with `--randomly-seed=<seed>` (pytest),
# `--sequence.seed=<seed>` (vitest), or `-- -Z unstable-options --shuffle-seed=<seed>` on a
# nightly `cargo test` (libtest). Run it when a test starts behaving as though a sibling
# left something behind, and after landing a batch of tests. Never in `just check`: its whole
# point is an order nobody chose, and a red the committer cannot reproduce is the one thing a
# pre-commit gate cannot absorb. It does run on a clock, weekly and on demand, on the one
# workflow that is not the gate mirror (`.github/workflows/shuffle.yml`, ADR-0002
# sweep-schedule addendum), where a red names its seed and blocks nothing. The Rust arm is a
# plain `cargo test` rather than the gate's coverage
# run, since the order is the only thing under test here and the coverage totals do not move.
shuffle seed="":
    #!/usr/bin/env bash
    set -euo pipefail
    seed="{{ seed }}"
    [ -n "$seed" ] || seed=$(( (RANDOM << 15) | RANDOM ))
    echo "=== shuffle seed: $seed (reproduce this run with: just shuffle $seed) ==="
    (cd brain && uv sync --locked && uv run pytest --randomly-seed="$seed")
    (cd scripts && uv sync --locked && uv run pytest --randomly-seed="$seed")
    (cd body/app && npm ci && npx vitest run --coverage --sequence.seed="$seed")
    (cd body && cargo +nightly test --locked --workspace -- -Z unstable-options --shuffle-seed="$seed")

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
