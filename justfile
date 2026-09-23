# `just check` runs every check. CI and the pre-commit hook run exactly these recipes.

default: check

# Every check: the thirteen repo-wide scans first, then the four per-tree checks in parallel,
# with each tree's output buffered and printed in a fixed order. Written for bash 3.2, which
# is what macOS ships.
check:
    #!/usr/bin/env bash
    set -euo pipefail
    just check-linecap
    just check-dashcheck
    just check-prosecheck
    just check-crosscheck
    just check-bindcheck
    just check-defaultcheck
    just check-volumecheck
    just check-stubcheck
    just check-samplecheck
    just check-rostercheck
    just check-flagcheck
    just check-settingscheck
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

# At most 300 lines per source file and 250 per markdown file, the generated backlog indexes
# excepted.
check-linecap:
    cd scripts && uv sync --locked
    cd scripts && uv run python linecap.py --root ..

# No dash as punctuation, in any text file across every tree.
check-dashcheck:
    cd scripts && uv sync --locked
    cd scripts && uv run python dashcheck.py --root ..

# No banned word from the table in AGENTS.md in any comment, docstring or document, and no
# docstring or comment block over three lines. Backticks, link targets, URLs and string
# literals are not read, so a file name or an identifier may use one of the words.
check-prosecheck:
    cd scripts && uv sync --locked
    cd scripts && uv run python prosecheck.py --root ..

# Every value written in more than one place still agrees with itself.
check-crosscheck:
    cd scripts && uv sync --locked
    cd scripts && uv run python crosscheck.py --root ..

# No compose bind mount creates a directory in the repo that git neither tracks nor ignores.
check-bindcheck:
    cd scripts && uv sync --locked
    cd scripts && uv run python bindcheck.py --root ..

# One variable named in several compose files has the same default in all of them, compared as
# a value: docker refuses `8.0g` as a size, so the subagent memory budget is written `8.0` in
# an environment block and `8` under the two limits that add the suffix.
check-defaultcheck:
    cd scripts && uv sync --locked
    cd scripts && uv run python defaultcheck.py --root ..

# Every volume an image declares is covered by a mount or a tmpfs in each service that runs it,
# so `docker compose down` leaves no anonymous volume behind. The scan cannot run docker, so it
# reads the record in scripts/imagevolumes.py; `just image-volumes` refreshes that record.
check-volumecheck:
    cd scripts && uv sync --locked
    cd scripts && uv run python volumecheck.py --root ..

# Every comment in proto/body.proto still appears in the committed Rust stub, which is the part
# of a skipped regeneration no compiler would catch. Regenerate the stub with `just proto`.
check-stubcheck:
    cd scripts && uv sync --locked
    cd scripts && uv run python stubcheck.py --root ..

# Every log line a runbook shows an operator still matches the call that writes it: level,
# logger, message and field names in the order the formatter prints them. Field values are not
# compared, because a captured value is only what one run produced.
check-samplecheck:
    cd scripts && uv sync --locked
    cd scripts && uv run python samplecheck.py --root ..

# Every list a document keeps of a real set still names that set: the modules in scripts/, the
# parts of the constant registry, and the others in scripts/rosters.py. Membership and naming
# only, since the sentence beside each name is what the list is for.
check-rostercheck:
    cd scripts && uv sync --locked
    cd scripts && uv run python rostercheck.py --root ..

# Every subagent server this repo starts has the flags its tier requires: both reasoning-off
# flags, the tool-capable chat template, and the host-RAM prompt cache turned off. The set of
# servers is derived from the compose wiring and argv rather than read from a list.
check-flagcheck:
    cd scripts && uv sync --locked
    cd scripts && uv run python flagcheck.py --root ..

# Every setting a brain module reads is named in the environment of the compose service that
# runs it, so a value set on the host reaches the container. A field left out deliberately is
# exempt in the scan with its reason, and an exemption that no longer applies fails.
check-settingscheck:
    cd scripts && uv sync --locked
    cd scripts && uv run python settingscheck.py --root ..

# Hand-run, needs docker and the network: pull every image this repo names, ask the daemon what
# each declares, and fail when scripts/imagevolumes.py disagrees. Run it after changing an image
# reference, after rebuilding an image here, and when a moving tag may have been republished.
image-volumes:
    cd scripts && uv sync --locked
    cd scripts && uv run python volumecheck.py --root .. --recompute

# Each backlog index still matches its task files, and every `#fragment` link in the repo names
# a heading its target really has. Regenerate the indexes with `just backlog`.
check-backlog:
    cd scripts && uv sync --locked
    cd scripts && uv run python backlogcheck.py --root ..

# Rewrite each backlog index from its task files. Run after closing or filing a task.
backlog:
    cd scripts && uv sync --locked
    cd scripts && uv run python backlogcheck.py --root .. --write

# Python brain workspace: format, lint, strict types, tests at 100% line and branch coverage.
check-brain:
    cd brain && uv sync --locked
    cd brain && uv run ruff format --check .
    cd brain && uv run ruff check .
    cd brain && uv run pyright
    cd brain && uv run pytest

# The check tooling in scripts/, checked exactly like any other Python in the repo.
check-scripts:
    cd scripts && uv sync --locked
    cd scripts && uv run ruff format --check .
    cd scripts && uv run ruff check .
    cd scripts && uv run pyright
    cd scripts && uv run pytest

# Rust body workspace: fmt, clippy, tests, then coverage at 100% line, region and branch.
# Branch coverage needs the nightly toolchain, and the second clippy line needs
# `rustup target add x86_64-pc-windows-msvc`; clippy never links, so no MSVC toolchain is needed.
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
    cd scripts && uv run python rustcoverage.py ../body/coverage.json --rustc "$(rustc +nightly --version)" --llvm-cov "$(cargo +nightly llvm-cov --version)"

# Clippy on the Tauri shell, for the host and for Windows. `just check` does not run it, because
# it is the only recipe that needs system libraries: the Linux GTK, webkit and dbus dev packages,
# and for the Windows target a resource compiler named by an absolute path. CI runs it instead.
check-shell:
    cd body/app/src-tauri && cargo clippy --locked --all-targets -- -D warnings
    cd body/app/src-tauri && RC_x86_64_pc_windows_msvc="${RC_x86_64_pc_windows_msvc:-/usr/bin/x86_64-w64-mingw32-windres}" cargo clippy --locked --target x86_64-pc-windows-msvc --all-targets -- -D warnings

# Overlay frontend (React and Vite): typecheck and Vitest at 100% line and branch coverage.
check-overlay:
    cd body/app && npm ci
    cd body/app && npm run typecheck
    cd body/app && npm run test:cov

# Run all four test suites in a shuffled order at one seed, printed so that a failure reproduces
# with `just shuffle <seed>`. `just check` uses a fixed seed instead, so this recipe is where the
# other orders come from. It also runs weekly from .github/workflows/shuffle.yml.
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

# Pick five commit bodies to replay, out of the twenty five most recent whose messages mention a
# mutation table, and report how many such commits there are since the last recorded pass. The
# pick is by seed, so `just replay <seed>` on the same commit picks the same five on any machine.
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
        echo "=== replay draw: seed $seed, over the candidate bodies committed since $since ==="
        echo "=== reproduce this draw with: just replay $seed $since, at $(git rev-parse --short HEAD) ==="
    else
        ledger="docs/runbooks/mutation-replay.md"
        anchor=""
        nearest=""
        for tip in $(sed -n 's/^| *[^|]* *| *\([0-9a-f]\{7,40\}\) *|.*/\1/p' "$ledger"); do
            git rev-parse --verify --quiet "$tip^{commit}" >/dev/null || continue
            ahead="$(git rev-list --count "$tip..HEAD")"
            if [ -z "$nearest" ] || [ "$ahead" -lt "$nearest" ]; then
                nearest="$ahead"
                anchor="$tip"
            fi
        done
        last="$(sed -n 's/^| \([0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}\) |.*/\1/p' "$ledger" | tail -n 1)"
        if [ -n "$anchor" ]; then
            when="$(sed -n "s/^| *\([^|]*[^| ]\) *| *$anchor *|.*/\1/p" "$ledger" | tail -n 1)"
            committed="$(git log "$anchor..HEAD" "${vocabulary[@]}" --format='%H')"
            read_as="the pass of $when, drawn from $(git rev-parse --short "$anchor")"
        elif [ -n "$last" ]; then
            committed="$(git log --since="$last" "${vocabulary[@]}" --format='%H')"
            read_as="midnight of the pass of $last, as no row records a commit this clone resolves"
        else
            read_as=""
        fi
        if [ -z "$read_as" ]; then
            echo "=== $ledger holds no commit and no dated row, so there is no current count ==="
        else
            behind="$(printf '%s' "$committed" | grep -c . || true)"
            due="no pass due"
            [ "$behind" -lt {{ window }} ] || due="a pass is due"
            echo "=== $behind candidate bodies since $read_as, cadence {{ window }}: $due ==="
        fi
        pool="$(git log --max-count={{ window }} "${vocabulary[@]}" --format='%H%x09%s')"
        echo "=== replay draw: seed $seed, over the {{ window }} most recent candidate bodies ==="
        echo "=== reproduce this draw with: just replay $seed, at $(git rev-parse --short HEAD) ==="
    fi
    candidates="$(printf '%s' "$pool" | grep -c . || true)"
    echo "=== $candidates candidate bodies, drawing {{ count }} ==="
    printf '%s\n' "$pool" | while IFS="$(printf '\t')" read -r sha subject; do
        [ -n "$sha" ] || continue
        printf '%s\t%s\t%s\n' "$(printf '%s:%s' "$seed" "$sha" | digest | cut -c1-16)" "$sha" "$subject"
    done | sort | sed -n '1,{{ count }}p' | cut -f2-

# Regenerate the committed gRPC stubs from proto/body.proto. Needs protoc installed locally.
proto:
    mkdir -p /tmp/protostage/cortex_seam/_generated
    cp proto/body.proto /tmp/protostage/cortex_seam/_generated/
    cd brain && uv run python -m grpc_tools.protoc -I /tmp/protostage --python_out=packages/seam/src --grpc_python_out=packages/seam/src --pyi_out=packages/seam/src /tmp/protostage/cortex_seam/_generated/body.proto
    cd body && CORTEX_REGEN_PROTO=1 cargo build -p body-rpc

# Run the brain without docker: BrainService on CORTEX_SEAM_HOST:CORTEX_SEAM_PORT.
brain-serve:
    cd brain && uv run python -m cortex_orchestrator

# Brain services in Compose, published on loopback only. `--project-directory .` keeps ./brain,
# ./sandbox, the .env file and the `cortex` project name resolving from the repo root.
up:
    docker compose --project-directory . -f docker/docker-compose.yml up -d --build

down:
    docker compose --project-directory . -f docker/docker-compose.yml down

# Brain plus a GPU llama-server for real inference. Needs an NVIDIA GPU and a models directory;
# see docs/runbooks/llamacpp-gpu.md. Never runs in CI, which has no GPU.
up-gpu:
    docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.gpu.yml up -d --build

down-gpu:
    docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.gpu.yml down

# Live check of the body to brain interface: the Rust integration suite, never run in CI. Needs a
# running brain (`just up` or `just brain-serve`) and CORTEX_SEAM_TOKEN set to the same value the
# brain serves with, because one test checks that a wrong token is refused.
rpc-health:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -z "${CORTEX_SEAM_TOKEN:-}" ]; then
        echo "CORTEX_SEAM_TOKEN is unset, so this suite cannot check that a wrong token is" >&2
        echo "refused: a brain serving without one accepts every token, and that check would fail" >&2
        echo "as if token checking had regressed. Serve with a token and present the same value:" >&2
        echo "    CORTEX_SEAM_TOKEN=<value> just up          # or just brain-serve" >&2
        echo "    CORTEX_SEAM_TOKEN=<value> just rpc-health" >&2
        echo "A token written in .env reaches compose, which reads that file, and not this" >&2
        echo "recipe, which does not. To check a token-free brain anyway, run the rest of the" >&2
        echo "suite by hand and say so in what you report:" >&2
        echo "    cd body && cargo test -p body-rpc --test live -- --ignored --nocapture \\" >&2
        echo "        --skip a_rejected_rpc_token" >&2
        exit 1
    fi
    cd body && cargo test -p body-rpc --test live -- --ignored --nocapture

# A local IMAP server used for testing: it can refuse a SELECT for a mailbox that exists and will
# not open, which the Bridge cannot be made to produce. Its own project, no mail, no password,
# loopback only. Procedure and results: docs/runbooks/email-imap.md.
up-imap-probe:
    docker compose --project-directory . -f docker/docker-compose.imap-probe.yml up -d --wait

down-imap-probe:
    docker compose --project-directory . -f docker/docker-compose.imap-probe.yml down

# Live folder-classification check against that probe. The address is read back from docker and
# tried twice, because a Docker Desktop engine publishes onto the Windows host, where a WSL distro
# beside it reaches only the container's own address. Integration-marked, never in CI.
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
        # The doubled braces are just's escape for a literal one, so docker is handed a plain
        # Go template that prints the address of whichever single network the container is on.
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

# Live inference check: streams a real completion through LlamaCppBackend. Needs `just up-gpu`;
# integration-marked, never in CI.
brain-inference-live:
    cd brain && CORTEX_INFERENCE_ENDPOINT=http://127.0.0.1:8080 uv run pytest -m integration --no-cov packages/inference

# End-to-end turn-cost measurement: three blocks in A/B/A order, each a brain container recreated
# with one environment variable changed, then `scripts/contrast.py` over the three samples. Needs
# a real GPU and the models directory, takes about 15 minutes at the default size, never in CI.
turn-cost arm="judge" control="raw" reps="8":
    #!/usr/bin/env bash
    set -euo pipefail
    compose="docker compose --project-directory . -f docker/docker-compose.yml"
    compose="$compose -f docker/docker-compose.gpu.yml -f docker/docker-compose.memory.yml"
    mkdir -p measurements
    # Bounded so that a brain which never becomes healthy fails here instead of waiting forever.
    # The healthcheck first probes at 15s and gives up after 3 retries at 30s.
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

# How wide the `dropped` field of the recall audit line gets, measured on lines a real brain
# container wrote. The probe runs inside the shipped image and `scripts/trailwidth.py` reads the
# captures back. Needs a real GPU and the models directory, takes about fifteen minutes.
recall-width blocks="2" passes="3" turns="8":
    #!/usr/bin/env bash
    set -euo pipefail
    compose="docker compose --project-directory . -f docker/docker-compose.yml"
    compose="$compose -f docker/docker-compose.gpu.yml -f docker/docker-compose.memory.yml"
    mkdir -p measurements
    health_wait=180
    $compose up -d --build
    # Both are set here because the audit line is off by default and the probe needs session
    # scoping, rather than trusting whatever configuration the stack came up with.
    CORTEX_MEMORY_SCOPE=session CORTEX_MEMORY_RECALL_AUDIT=1 \
        $compose up -d --no-deps --force-recreate brain
    deadline=$((SECONDS + health_wait))
    until $compose ps brain | grep -q '(healthy)'; do
        if [ "$SECONDS" -ge "$deadline" ]; then
            echo "brain never reported (healthy) in ${health_wait}s" >&2
            $compose ps brain >&2
            echo "diagnose with: $compose logs brain" >&2
            exit 1
        fi
        sleep 1
    done
    $compose cp brain/packages/inference/tests/recall_corpus.py brain:/tmp/recall_corpus.py
    $compose cp brain/packages/orchestrator/tests/recall_trail_probe.py brain:/tmp/probe.py
    captures=()
    for block in $(seq 1 {{ blocks }}); do
        echo "=== block $block of {{ blocks }} ==="
        started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
        probed="measurements/trail-width-$block-direct.log"
        served="measurements/trail-width-$block-turns.log"
        $compose exec -T -e PYTHONPATH=/tmp -e CORTEX_TRAIL_DIRECT_PASSES={{ passes }} \
            -e CORTEX_TRAIL_TURNS={{ turns }} brain python /tmp/probe.py >"$probed" 2>&1
        $compose logs brain --since "$started" >"$served" 2>&1
        captures+=("../$probed" "../$served")
    done
    cd scripts && uv sync --locked
    uv run python trailwidth.py "${captures[@]}"

# Print what each variant of an envelope measurement did, refusing the comparison when the control
# variant is proven to succeed on less than nine tenths of its own runs. Reads samples the live
# driver wrote, so it needs no GPU; `--project` keeps the sample paths that driver printed.
envelope-floor +samples:
    uv sync --locked --project scripts
    uv run --project scripts python scripts/envelopefloor.py {{ samples }}

# Count the cells that two or more seeded runs of one envelope variant produced identically, in
# output and in tokens, for every pair of runs. Refuses when a seed is null, when two samples do
# not contain the same cells, or when a matched cell was a different variant, instruction or body.
envelope-pairs +samples:
    uv sync --locked --project scripts
    uv run --project scripts python scripts/envelopepairs.py {{ samples }}

# Print what each tier's chat template rendered for the thinking switch and compare it with what
# the same run measured, refusing to publish when the two disagree. Reads samples the live probe
# wrote, so it needs no GPU.
switch-tail +samples:
    uv sync --locked --project scripts
    uv run --project scripts python scripts/switchtail.py {{ samples }}

# The gpu stack plus a loopback publish of the model-host control API, which the gpu override
# leaves unpublished because it can start and stop GPU processes. For live tests only;
# `just down-gpu` takes it down. Procedure: docs/runbooks/model-swap.md.
up-modelhost-loopback:
    docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.gpu.yml -f docker/docker-compose.modelhost-loopback.yml up -d --build

# Live model-host check: starts, health-checks and stops a real llama-server through the real
# ModelHost adapter. Needs `just up-modelhost-loopback`; integration-marked, never in CI.
brain-modelhost-live:
    cd brain && CORTEX_MODELHOST_ENDPOINT=http://127.0.0.1:9300 uv run pytest -m integration --no-cov packages/model_manager
