# `just check` is THE gate (AGENTS.md gate 6): CI and pre-commit run exactly these
# recipes. If it passes here, it passes there.

default: check

# All gates: the eleven cross-tree scans first (fast), then the four tree checks in
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
    just check-defaultcheck
    just check-volumecheck
    just check-stubcheck
    just check-samplecheck
    just check-rostercheck
    just check-flagcheck
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

# One variable spelled in several compose files still carries one default in all of them,
# compared as a value so the one deliberate re-spelling in the tree stays green: docker reads
# `8.0g` as a size and refuses it, so the subagent memory budget is written `8.0` in an
# environment block and `8` under the two limits that suffix it.
check-defaultcheck:
    cd scripts && uv sync --locked
    cd scripts && uv run python defaultcheck.py --root ..

# Every volume an image declares is covered by a mount or a tmpfs in every compose service
# that runs it, so no container quietly collects an anonymous volume `down` then leaves on
# the host. What an image declares is a fact about a registry rather than about this tree,
# so it is recorded in scripts/imagevolumes.py and this scan reads the record; `just
# image-volumes` is what re-derives that record from docker and fails when it has gone
# stale (ADR-0011 addendum on evidence out of the gate's reach). Three of those rows are
# built here, and for those the same scan reads the Dockerfile each build stanza points at
# and fails when it declares, or inherits from the image its last stage stands on, or would
# be handed by that image's own ONBUILD, a path its row does not carry. That is the half of
# the question the tree can answer with no daemon at all, and it is a floor under what a
# built image declares rather than the whole of it, which is why those three rows are
# recorded rather than derived from the sides.
check-volumecheck:
    cd scripts && uv sync --locked
    cd scripts && uv run python volumecheck.py --root ..

# Every comment proto/body.proto carries still appears in the committed Rust seam stub,
# which is the one part of a stale regeneration nothing else would notice: a renamed field
# breaks the compile, while a retuned number stated in a comment goes on being read. It is
# a text comparison and runs no codegen, so it needs neither protoc nor a GPU. Regenerate
# with `just proto`.
check-stubcheck:
    cd scripts && uv sync --locked
    cd scripts && uv run python stubcheck.py --root ..

# Every log line a runbook prints back to an operator still says what the call site that
# writes it would print: the level, the logger, the message, and the fields in the order the
# formatter renders them, which is name order. Field VALUES are deliberately not held, one
# runbook's captured port being a dated reading rather than a coupling. The samples are found
# rather than registered, so a new one is held the day it is written (ADR-0009 addendum on a
# sample's membership).
check-samplecheck:
    cd scripts && uv sync --locked
    cd scripts && uv run python samplecheck.py --root ..

# Every roster a document keeps still names the set it describes: the ignored checks in the
# body's live seam suite, the modules in scripts/, the tuples the constant registry is joined
# from. Membership and naming only. The sentence beside each name is what a roster is FOR and
# is deliberately unheld, as is any tally beside it, a count restated by hand being the half
# that drifts first. A roster's two boundary phrases are data, so a passage that slid out from
# under them fails rather than quietly shrinking what is compared.
check-rostercheck:
    cd scripts && uv sync --locked
    cd scripts && uv run python rostercheck.py --root ..

# Every subagent server this repo starts carries the flags its tier requires: the reasoning-off
# pair, because neither flag alone covers both request shapes the tier serves and a server with
# half of it spends its whole cap on a trace no reader ever sees, and the tool-capable chat
# template, without which a tools-enabled subagent silently has no tools. The set of servers is
# DERIVED rather than registered: a service is one when the brain's subagent wiring dials its
# address or when its own argv names a subagent model file, so an override adding a server is held
# the day it is written rather than the day somebody remembers to list it (ADR-0029 addendum on
# deriving the set a rule runs over).
check-flagcheck:
    cd scripts && uv sync --locked
    cd scripts && uv run python flagcheck.py --root ..

# Hand-run, needs docker and the network: pull every image this repo names, ask the daemon
# what each actually declares and what each would declare for a child through ONBUILD, and
# fail when scripts/imagevolumes.py disagrees in either. The pull is
# the point, since inspect answers out of the local cache and most of these references are
# moving tags; the three images built here are asked without one, having no registry, which
# is why the two bases they stand on have rows of their own and are pulled like the rest. A
# built row is therefore whatever the machine running this last built, and the gate holds it
# to a base that is current. Run it after pinning a new image or bumping a pinned one, on
# any day a moving tag may have been republished, and after rebuilding an image here, since
# that record is the only thing check-volumecheck can see.
image-volumes:
    cd scripts && uv sync --locked
    cd scripts && uv run python volumecheck.py --root .. --rederive

# Each backlog index still matches the task files it describes (ADR-0039). A task's
# status lives on its own Status line and nowhere else, so this is the only thing
# holding the generated index to it. It also holds every fragment written anywhere in
# the repo to naming a heading its target really offers, so no rename can leave a
# resolving link on a heading nobody renders. Regenerate with `just backlog`.
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
# x86_64-pc-windows-msvc); clippy never links, so no MSVC toolchain is needed. Shell CLIPPY
# stays out of this recipe and has its own, `check-shell` below, because it needs the Linux
# GTK/webkit/dbus dev packages that this recipe deliberately does not.
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
# BOTH RELAYS ARE REQUIRED ARGUMENTS OF THE GATE (ADR-0002 mandatory-relay addendum), so dropping
# either from the line below is a usage error, exit 2, and not a quieter gate. Required is not
# non-empty, and what covers the difference is this line's own shape: both substitutions run in ONE
# shell, so the toolchain that empties one empties the other, and an empty `--llvm-cov` fails loudly
# as a producer mismatch where an empty `--rustc` would print `measured by` and pass. Filling either
# from anywhere else (a second shell, an env var, a file, a CI step's output) brings that quiet half
# back and is what the empty-relay addendum declined a validator against. While they were
# optional, deleting `--llvm-cov` deleted the producer cross-check with no complaint: the run
# printed the same five green lines a real pass prints and exited 0.
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

# The Tauri shell (body/app/src-tauri), clippied rather than only fmt-checked. THE ONE
# `check-*` RECIPE `just check` DOES NOT RUN, and the only place CI runs a gate a local
# `just check` does not (ADR-0011 shell-clippy addendum). Unlike every other recipe here it
# needs system libraries: the shell has to actually compile for clippy to see it, which means
# the Linux GTK/webkit/dbus dev packages providing the pkg-config metadata the `-sys` build
# scripts probe for. A runner installs those with one apt line; a dev box may have none of
# them, and requiring them would make the single gate unrunnable on a clean checkout, which is
# worse than the divergence. So CI owns the schedule and this recipe owns the check, and it is
# path-filtered onto shell edits alone (ci_paths.py routes body/app/src-tauri/ to `rust+shell`),
# so no other `body/` change pays for it. Clippy never LINKS, so the metadata is all that is
# needed and none of those libraries is ever loaded; a sudo-less host runs it with
# PKG_CONFIG_PATH naming an unpacked prefix, which that addendum records.
check-shell:
    cd body/app/src-tauri && cargo clippy --locked --all-targets -- -D warnings

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

# The replay pass's draw (ADR-0002 replay-cadence addendum). A mutation table is a self report
# until somebody other than its author re-runs it, so a pass replays a SAMPLE of the record:
# five commit bodies out of the twenty five most recent that carry a table. The draw is the half
# that has to be blind. An agent choosing by hand chooses what it already understands, and the
# tables most worth replaying are exactly the ones nobody can reconstruct, so the sample is drawn
# by seed and the seed is printed: `just replay <seed>` draws the same five on any machine, the
# key being a digest of the seed and the commit rather than a shuffler whose stream is a property
# of the local coreutils. Hand a date as the second argument to ask the OTHER question this pass
# needs answered, how many tables have landed since the last one, which is what says whether a
# pass is due: the cadence is counted in tables and not in days, because this record grows in
# bursts. Procedure, the rule for a row that does not reproduce, and the ledger of passes:
# docs/runbooks/mutation-replay.md. This gates nothing and runs on no clock; a replay needs the
# judgement to rebuild an edit from a sentence, which is why it is not a workflow.
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

# Live seam check from the body side: the Rust integration suite (#[ignore]-marked, never in
# CI/coverage per ADR-0003). It needs two things, and the second one used to go unsaid. A
# running brain (`just up` or `just brain-serve`), and a seam token (ADR-0016) served by that
# brain and presented here as the same value, because one check in the suite proves a wrong
# token is refused at once and a brain serving without one accepts every token there is,
# including the deliberately wrong one. So the token is checked before the build rather than
# left to fail deep in a run: a red check meaning "you configured it wrong" is indistinguishable
# at a glance from one meaning "the seam regressed", and the recipe that gave the instructions
# is the right place to tell them apart.
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

# The IMAP probe: a second, local IMAP server that can refuse a SELECT for the other reason,
# a mailbox that exists and will not open, which the Bridge cannot be made to produce. It is a
# measurement fixture and not part of the brain stack: its own project, no mail, no password,
# loopback only. Procedure and the answers it gave: docs/runbooks/email-imap.md.
up-imap-probe:
    docker compose --project-directory . -f docker/docker-compose.imap-probe.yml up -d --wait

down-imap-probe:
    docker compose --project-directory . -f docker/docker-compose.imap-probe.yml down

# Live folder-classification check against that probe. Where the server answers is read back off
# docker rather than written here a second time, so an overridden publish still reaches the right
# server, and it is read in two steps because one is not enough everywhere. The publish is asked
# first, being what the compose file requests and what a Linux engine gives. It is not what every
# dev box gets: a Docker Desktop engine publishes onto the Windows host, so a WSL distro beside it
# reaches the container's own address on the bridge and never the published port, and a recipe that
# only knew the publish sat there until somebody killed it. So the publish is probed, the
# container's address is the fallback, and a probe that answers at neither says so and stops.
# Integration-marked, never in CI.
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

# How wide the recall trail's `dropped` field really gets, read off lines the brain container
# wrote (ADR-0038 real-trail addendum). `VALUE_CHARS` is argued against that width, and the figure
# it was argued against was synthesised in process from uuid4 ids and made-up cosines; this is what
# reads it off a live stack instead. THE DOCKER LIVES HERE for the reason it lives in `turn-cost`:
# the probe runs INSIDE the shipped image, so copying it in and capturing what it wrote is a
# deployment step rather than an assertion, and `scripts/trailwidth.py` reads the captures back.
# Two blocks by default, because the claim is about a maximum and one sample of a maximum proves
# nothing; each block ends with real turns over the seam, whose trail lines come back through the
# container's log driver rather than off the probe's own stream. Needs a real GPU, the models dir
# and roughly fifteen minutes; never runs in CI. Runbook: docs/runbooks/memory-pgvector.md.
recall-width blocks="2" passes="3" turns="8":
    #!/usr/bin/env bash
    set -euo pipefail
    compose="docker compose --project-directory . -f docker/docker-compose.yml"
    compose="$compose -f docker/docker-compose.gpu.yml -f docker/docker-compose.memory.yml"
    mkdir -p measurements
    health_wait=180
    $compose up -d --build
    # The trail is off by default and the probe refuses to run under global scoping, so the brain
    # is recreated with both set rather than trusting whatever the stack came up with.
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

# What an envelope measurement's arms did, published only while its control arm still stands
# (ADR-0028 control-arm addendum). The driver
# (brain/packages/orchestrator/tests/test_envelope_cost_live.py) writes one sample per arm and
# computes nothing, for the reason the turn-cost driver computes nothing: a published number's
# arithmetic belongs in a covered file. This is that file, and it also holds the arm every rate is
# read against to nine tenths of its own runs, refusing to print a comparison when a control cell
# is proven below it, since a difference read against a control that failed the subtask prices the
# pick and not the envelope. Unlike every other recipe here it runs the tree from where it is
# rather than from inside it, `--project` instead of a `cd`, so the sample paths are the driver's
# own: that run writes them relative to `brain/` and prints them resolved, and a reader pasting
# either that line or a path of their own gets the file they named. Gates nothing and needs no
# GPU: the run that produced the samples needed one.
envelope-floor +samples:
    uv sync --locked --project scripts
    uv run --project scripts python scripts/envelopefloor.py {{ samples }}

# The gpu stack PLUS a loopback publish of the model-host control API, which the base gpu override
# deliberately withholds (it can start and stop GPU processes, ADR-0030 d3). For live tests only;
# `just down-gpu` takes it down. Procedure: docs/runbooks/model-swap.md.
up-modelhost-loopback:
    docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.gpu.yml -f docker/docker-compose.modelhost-loopback.yml up -d --build

# Live model-host check: starts, health-gates and stops a real llama-server through the real
# ModelHost adapter. Needs `just up-modelhost-loopback`; integration-marked, never in CI/coverage.
brain-modelhost-live:
    cd brain && CORTEX_MODELHOST_ENDPOINT=http://127.0.0.1:9300 uv run pytest -m integration --no-cov packages/model_manager
