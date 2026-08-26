# `just check` is THE gate (AGENTS.md gate 6): CI and pre-commit run exactly these
# recipes. If it passes here, it passes there.

default: check

check:
    #!/usr/bin/env bash
    set -euo pipefail
    just check-linecap
    just check-dashcheck
    just check-crosscheck
    just check-bindcheck
    just check-defaultcheck
    just check-volumecheck
    just check-stubcheck
    just check-samplecheck
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

check-defaultcheck:
    cd scripts && uv sync --locked
    cd scripts && uv run python defaultcheck.py --root ..

check-volumecheck:
    cd scripts && uv sync --locked
    cd scripts && uv run python volumecheck.py --root ..

check-stubcheck:
    cd scripts && uv sync --locked
    cd scripts && uv run python stubcheck.py --root ..

check-samplecheck:
    cd scripts && uv sync --locked
    cd scripts && uv run python samplecheck.py --root ..

image-volumes:
    cd scripts && uv sync --locked
    cd scripts && uv run python volumecheck.py --root .. --rederive

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

check-shell:
    cd body/app/src-tauri && cargo clippy --locked --all-targets -- -D warnings

check-overlay:
    cd body/app && npm ci
    cd body/app && npm run typecheck
    cd body/app && npm run test:cov

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

replay seed="" since="" count="5" window="25":
    #!/usr/bin/env bash
    set -euo pipefail
    seed="{{ seed }}"
    [ -n "$seed" ] || seed=$(( (RANDOM << 15) | RANDOM ))
    case "$seed" in
        *[!0-9]*)
            echo "a seed must be digits only, got '$seed'" >&2
            exit 1
            ;;
    esac
    if command -v sha256sum >/dev/null 2>&1; then
        digest() { sha256sum; }
    elif command -v shasum >/dev/null 2>&1; then
        digest() { shasum -a 256; }
    else
        echo "the draw needs sha256sum or shasum on PATH to be reproducible" >&2
        exit 1
    fi
    vocabulary=(-i -E --grep='redden' --grep='mutant' --grep='mutation' --grep='prove[a-z]* able to fail')
    since="{{ since }}"
    if [ -n "$since" ]; then
        pool="$(git log --since="$since" "${vocabulary[@]}" --format='%H%x09%s')"
        echo "=== replay draw: seed $seed, over the tables landed since $since ==="
        echo "=== reproduce this draw with: just replay $seed $since ==="
    else
        pool="$(git log --max-count={{ window }} "${vocabulary[@]}" --format='%H%x09%s')"
        echo "=== replay draw: seed $seed, over the {{ window }} most recent tables ==="
        echo "=== reproduce this draw with: just replay $seed ==="
    fi
    candidates="$(printf '%s' "$pool" | grep -c . || true)"
    echo "=== $candidates candidate bodies, drawing {{ count }} ==="
    printf '%s\n' "$pool" | while IFS="$(printf '\t')" read -r sha subject; do
        [ -n "$sha" ] || continue
        printf '%s\t%s\t%s\n' "$(printf '%s:%s' "$seed" "$sha" | digest | cut -c1-16)" "$sha" "$subject"
    done | sort | sed -n '1,{{ count }}p' | cut -f2-

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

seam-health:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -z "${CORTEX_SEAM_TOKEN:-}" ]; then
        echo "CORTEX_SEAM_TOKEN is unset, so this suite cannot check that a wrong token is" >&2
        echo "refused: a brain serving without one accepts every token, and that check would" >&2
        echo "fail as if the seam had regressed. Serve with a token and present the same value:" >&2
        echo "    CORTEX_SEAM_TOKEN=<value> just up          # or just brain-serve" >&2
        echo "    CORTEX_SEAM_TOKEN=<value> just seam-health" >&2
        echo "A token written in .env reaches compose, which reads that file, and not this" >&2
        echo "recipe, which does not. To check a token-free brain anyway, run the rest of the" >&2
        echo "suite by hand and say so in what you report:" >&2
        echo "    cd body && cargo test -p body-rpc --test live -- --ignored --nocapture \\" >&2
        echo "        --skip a_rejected_seam_token" >&2
        exit 1
    fi
    cd body && cargo test -p body-rpc --test live -- --ignored --nocapture

up-imap-probe:
    docker compose --project-directory . -f docker/docker-compose.imap-probe.yml up -d --wait

down-imap-probe:
    docker compose --project-directory . -f docker/docker-compose.imap-probe.yml down

email-folder-probe:
    #!/usr/bin/env bash
    set -euo pipefail
    compose=(docker compose --project-directory . -f docker/docker-compose.imap-probe.yml)
    served=143
    published="$("${compose[@]}" port imap-probe "$served")"
    host="${published%:*}"
    port="${published##*:}"
    answers() { timeout 3 bash -c "exec 3<>/dev/tcp/$1/$2" 2>/dev/null; }
    if ! answers "$host" "$port"; then
        # The doubled braces are just's own escape for a literal one, so what docker is handed
        # is the plain Go template that prints the address of whatever single network it is on.
        host="$(docker inspect -f '{{{{range .NetworkSettings.Networks}}{{{{.IPAddress}}{{{{end}}' \
            "$("${compose[@]}" ps -q imap-probe)")"
        port="$served"
        answers "$host" "$port" || {
            echo "the probe answers at neither $published nor $host:$port; run \`just up-imap-probe\`" >&2
            exit 1
        }
    fi
    cd brain && CORTEX_EMAIL_PROBE_HOST="$host" CORTEX_EMAIL_PROBE_PORT="$port" \
        uv run pytest -m integration --no-cov packages/email/tests/test_imap_probe_live.py

# Live inference check: streams a real completion through LlamaCppBackend. Needs the gpu
# stack up (`just up-gpu`); integration-marked, never in CI/coverage (ADR-0007).
brain-inference-live:
    cd brain && CORTEX_INFERENCE_ENDPOINT=http://127.0.0.1:8080 uv run pytest -m integration --no-cov packages/inference

turn-cost arm="judge" control="raw" reps="8":
    #!/usr/bin/env bash
    set -euo pipefail
    compose="docker compose --project-directory . -f docker/docker-compose.yml"
    compose="$compose -f docker/docker-compose.gpu.yml -f docker/docker-compose.memory.yml"
    mkdir -p measurements
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
