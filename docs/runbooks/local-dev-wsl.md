# Runbook for local development on WSL

The daily loop for working on Cortex from a WSL2 distro. Rules live in
[AGENTS.md](../../AGENTS.md); gate mechanics in
[ADR-0002](../adr/ADR-0002-toolchain-checks.md); seam codegen, packaging, and the seam
config contract in [ADR-0003](../adr/ADR-0003-seam-codegen.md).

## Prerequisites (one-time, inside the distro)

- **uv** runs every Python project (the `brain/` workspace and `scripts/`).
- **rustup** with **stable** (default) plus **nightly** for branch coverage only
  (ADR-0002 d1): `rustup toolchain install nightly --component llvm-tools-preview`.
- **The `x86_64-pc-windows-msvc` target** on stable, so `check-body` can clippy the
  `cfg(windows)` `os_windows` backend the native workspace compiles to nothing (ADR-0011):
  `rustup target add x86_64-pc-windows-msvc`. Clippy never links, so no MSVC toolchain is
  needed; on a Windows host this target is already the native one.
- **cargo-llvm-cov** installs via `cargo install cargo-llvm-cov`.
- **Neither of those two is pinned to a version, by decision** (the
  [ADR-0002](../adr/ADR-0002-toolchain-checks.md) toolchain-print addendum), so this machine and CI
  routinely resolve different ones. `check-body` therefore prints `rustc +nightly --version` and
  `cargo +nightly llvm-cov --version` before it measures, and hands both to the gate, whose verdict
  repeats them next to the numbers they produced:

  ```
  measured by cargo-llvm-cov 0.8.7, llvm export 3.1.0
  measured by rustc 1.98.0-nightly (4c9d2bfe4 2026-07-01)
  PASS lines: 100.00%
  ```

  When the coverage gate fails, read those lines against the ones in a CI log first: a toolchain
  that moved and a commit that broke coverage look identical in the totals and nowhere else. CI
  installs the channel fresh every run, so its compiler is the one dated on the day that run
  happened, which the version string carries. Two failures here are about the report rather than
  the code. `FAIL producer:` means the `body/coverage.json` being judged was written by a different
  cargo-llvm-cov than the one that just ran, so re-run the measurement rather than reading its
  numbers. `coverage report has no 'cargo_llvm_cov' entry` means the export stopped naming its
  writer, which the gate treats as a failure by design (ADR-0002 single-verdict addendum).
- **just** provides `just check`, THE gate (AGENTS.md gate 6); run it before calling
  anything done.
- **Every suite in that gate runs shuffled under a fixed seed** (the
  [ADR-0002](../adr/ADR-0002-toolchain-checks.md) shuffle addendum): `--randomly-seed=9973` in
  `brain/pyproject.toml`, `7919` in `scripts/pyproject.toml`, `sequence: { shuffle: true, seed:
  65537 }` in `body/app/vite.config.ts`, and `-- -Z unstable-options --shuffle-seed=104729` on
  `check-body`'s coverage step in the `justfile`. So the order is not the collection order and is
  still the
  same order twice; a red run reproduces exactly, here and in CI, and pytest prints
  `Using --randomly-seed=N` in its header so the log names the order it ran in. Reproducing a
  failure needs nothing special, but reproducing it in ISOLATION does: pass the seed the header
  printed, `uv run pytest --randomly-seed=9973 <path>`, or the test will run in a different order
  than the failing run did. Do not tune a seed to make a test pass; that throws away every draw
  the suite has survived and hides the dependency rather than fixing it.
- **The Rust arm is the one with different mechanics** (the same ADR's rust-shuffle addendum), so
  read this before trying to reproduce a failure there. It rides the nightly coverage step
  because libtest's shuffle is nightly-only behind `-Z unstable-options` and every other Rust gate
  stays on stable, so `just check` runs that suite twice, alphabetically and permuted, and both
  must pass. Each test binary prints `running N tests (shuffle seed: 104729)`. Reproducing one
  binary in isolation is
  `cargo +nightly test -p body-rpc --test body_server -- -Z unstable-options --shuffle-seed=104729`,
  and adding `--test-threads=1` is what makes the order readable, libtest permuting dispatch into
  parallel threads rather than running serially. Unlike pytest, adding one test re-draws its whole
  binary, so a red there can name a pair you did not touch.
- **`just shuffle [seed]`** is the deliberate sweep, and the one thing `just check` does not do:
  all four suites at ONE seed of your choosing, a random one by default, printed so the run
  reproduces with `just shuffle <seed>`. Run it when a test behaves as though a sibling left
  something behind, and after landing a batch of tests. It stays out of the gate because its point
  is an order nobody chose, and a pre-commit gate cannot absorb a red the committer cannot
  reproduce.
- **A weekly workflow runs that sweep** (the same ADR's sweep-schedule addendum):
  `.github/workflows/shuffle.yml` draws a seed every Monday, and takes one from the Actions tab on
  demand, so the pairs the frozen seeds never draw get re-drawn without anyone remembering. It is the
  one workflow here that is not the `just check` mirror: it gates nothing, is a required check on
  nothing, and a red there blocks no merge and no push. Read such a red as a real order dependency
  between two tests that already coexisted, so it is not about whatever commit was at the head; the
  run's summary names the seed and the `just shuffle <seed>` that replays the whole thing locally.
  Fix the test, never the seed. Two operational notes: dispatching it with a seed re-runs a red at
  its own order without a local checkout, and GitHub disables a schedule on a public repository
  after 60 days of no activity, which is the one way this becomes a sweep that cannot fire.
- **pre-commit** needs `pre-commit install` once; the hook is a literal `just check`
  (ADR-0002 d9).
- **protoc 35.x** is needed only to regenerate the committed seam stubs (`just proto`,
  ADR-0003 d1); normal builds and CI never invoke it.
- **Docker Desktop on Windows** with WSL integration enabled for this distro
  (Settings → Resources → WSL integration). The daemon runs on Windows; the
  `docker` / `docker compose` CLIs inside WSL talk to it, and ports published on
  `127.0.0.1` are reachable from both WSL and Windows. The base compose is GPU-free;
  real inference is the opt-in `docker/docker-compose.gpu.yml` override (Slice 4,
  see [llamacpp-gpu.md](llamacpp-gpu.md)).
  Footgun: `docker-credential-desktop.exe … exec format error` means the shell lacks
  WSL interop (Docker Desktop's credential helper is a Windows binary); run from a
  shell with interop, or point `DOCKER_CONFIG` at a config without a `credsStore`.

## Configuration (env only)

| Variable | Default | Read by |
|---|---|---|
| `CORTEX_SEAM_HOST` | `127.0.0.1` | brain server bind host (Compose sets `0.0.0.0` inside the container; exposure stays loopback-only via the port publish) |
| `CORTEX_SEAM_PORT` | `50051` | brain server bind port |
| `CORTEX_SEAM_TOKEN` | *(empty, auth off)* | both directions (ADR-0016/0023): the brain server rejects untokened body→brain calls when set (Compose passes it through from the host env/`.env`); the body server now validates the same token on brain→body calls and the brain client attaches it when dialing the body; the body/live checks present the same value |
| `CORTEX_REDIS_URL` | `redis://127.0.0.1:6379/0` | brain composition root (where session state lives; Compose sets `redis://redis:6379/0`) |
| `CORTEX_MODEL_CORTEX` | `cortex` | brain composition root (the LOGICAL cortex model id (ADR-0004), never a path) |
| `CORTEX_BRAIN_ADDR` | `http://127.0.0.1:50051` | body-side live check (the address it dials) |
| `CORTEX_BODY_BACKEND` | `none` | brain composition root (ADR-0023, the brain→body direction); `none` (off) or `grpc` (dial the host body, wiring the `get_volume`/`set_volume` tools) |
| `CORTEX_BODY_ENDPOINT` | *(required when `grpc`)* | brain composition root (the host body the brain dials; `host.docker.internal:50151` from the dockerized brain) |
| `CORTEX_BODY_ADDR` | `127.0.0.1:50151` | body server bind addr (ADR-0023); set `0.0.0.0:50151` for the real container→host path (seam token + host firewall are then the boundary) |

The defaults line up: a brain on defaults is reachable by a body check on defaults and
finds a redis published by Compose on loopback. Everything listens on loopback only
(ROADMAP assumption 5). The brain→body direction (`CORTEX_BODY_*`, the first host OS
action, reading and setting system volume) has its own end-to-end validation in
[body-volume.md](body-volume.md).

### How the composed brain receives a setting

The brain container gets only the variables its compose files name, so a setting exported in
the shell or written in the repo-root `.env` reaches it only when some file layered on names
that variable. Each of the brain's settings is named in one of three ways:

- **Passed through by name**, a bare key such as `CORTEX_OUTPUT_GUARDRAIL:`. Set on the host,
  the value reaches the brain; unset, the variable never enters the container and the settings
  class's own default applies. The base file passes the settings that apply to every stack
  (history window, output guardrail, titles, reply bounds, seam buffer and confirm timeout, VRAM
  budget, tool gating, costs and audit file, schedule pacing). Each overlay passes the ones its
  capability reads: `docker-compose.gpu.yml` the inference and handoff settings and the two
  logical model ids, `docker-compose.memory.yml` the recall settings, `docker-compose.subagents.yml`
  the delegation bounds.
- **Passed with a compose default**, `${CORTEX_X:-value}`, where the default is spelled in the
  compose file as well as in Python (`CORTEX_SEAM_TOKEN`, `CORTEX_LOG_FORMAT`, the tool salience
  knobs and call timeout, the schedule backend and zone, the body settings, the subagent resource
  figures). `scripts/crosscheck.py` holds the body and subagent figures to their Python
  declarations; the others are not held, which is why a new setting is passed bare.
- **Set by the file**, where the topology decides the value: `CORTEX_SEAM_HOST`,
  `CORTEX_REDIS_URL`, each overlay's backend switch and in-network endpoints, and the memory DSN.
  Setting one of these on the host has no effect.

Two settings are named by no file, on purpose. `CORTEX_SEAM_PORT` is fixed at 50051 by the base
file's publish and its healthcheck, and `CORTEX_TOOLS_ENDPOINT` is the single-sidecar form that
the tool overlays replace with one `CORTEX_TOOLS_ENDPOINTS__<name>` key each (the brain refuses
both at once). The map-shaped settings `CORTEX_TOOLS_ALLOW` and `CORTEX_SUBAGENTS_ROSTER` are
contributed one key at a time by the overlay that brings the server they describe.
`just check-settingscheck` fails when a settings field reaches its service from no file and is not
one of those two, and it holds the model host and the email sidecar the same way; a new setting
therefore lands with its key. To see what a given stack will hand the brain, render it without
starting anything:

```bash
docker compose --project-directory . -f docker/docker-compose.yml [-f <overlay> ...] config brain
```

A key rendered as `null` is a pass-through whose variable is unset on the host.

## Redis (the session store)

Compose runs a `redis` service (image `redis:8-alpine`) next to the brain. Why Redis
over Valkey: redis-py and fakeredis (our client and its contract-test twin) track
Redis semantics first, and Redis 8 is available under an open-source license again
(AGPLv3 option), so there is no license pressure on a local single-user deployment.

- **Persistence:** `--appendonly yes` with the named volume `redis-data`, so sessions
  survive a redis restart too. `docker compose down -v` is the reset switch (wipes all
  conversations).
- **Inspection from the host** (the port is published on `127.0.0.1` only):

  ```sh
  docker compose exec redis redis-cli keys 'cortex:session:*'
  docker compose exec redis redis-cli lrange 'cortex:session:<session-id>:messages' 0 -1
  ```

  One JSON document per message (`{"role", "text", "at", "turn_id"}`, whose layout
  contract is in [modules/brain-session.md](../modules/brain-session.md)).

**State survives a brain restart (the Slice 3 acceptance).** Conversation state lives
only in redis (the one hard rule), so a plain `docker compose restart brain` preserves
every conversation: run a turn, restart the brain container (redis keeps running), run
another turn in the same session. The deterministic reply counter keeps counting
(`reply 1: …`, then `reply 2: …`).

## Run the brain

Natively, for fast iteration (uv syncs automatically). Needs a reachable redis, e.g.
just the Compose redis service:

```sh
docker compose up -d redis
cd brain && uv run python -m cortex_orchestrator
```

In Compose, the deployed shape (from the repo root):

```sh
docker compose up -d --build
docker compose ps            # wait for "healthy" (the brain healthcheck calls the real Health RPC)
docker compose logs -f brain
docker compose down
```

## Read the brain's logs

`docker compose logs brain` is where every diagnosis in these runbooks ends up, and since the
ADR-0038 rendered-fields addendum a line carries the fields the code attached to it rather than
the message alone:

```text
brain-1  | INFO:cortex_orchestrator.server:seam server listening host=0.0.0.0 port=50051
```

Everything after the message is `key=value` pairs in **name order**, which is what makes two lines
of the same kind comparable column by column and what makes `grep "capped=True"` work. Three
reading rules:

- A scalar is written the way Python writes it, so a boolean reads `True` and not `true`.
- A value carrying whitespace or a quote is quoted (`error="permission denied"`), so it stays one
  field.
- Anything structured is compact JSON (`hits=[{"id":"m1","score":0.87}]`), so it can be pasted
  into `jq` or read as it stands.

**The message says what happened and the fields say what it happened to**, so a value appears once
on the line. A message is a constant sentence: `started a model process model=cortex pid=41
port=8081`, never that sentence with `model=cortex pid=41 port=8081` written into it as well. That
is what makes the greps in these runbooks match on a message's words and read the values out of the
fields beside them, and it is why `docker compose logs brain | grep "could not be asked"` finds
every control call the sidecar left unanswered, however many tiers and errors they name. Two kinds
of line still carry a value in their prose, and neither is a field printed twice: one whose message
the code also raises as an exception's text, which has to read on its own where no formatter runs,
and one whose sentence needs a word to finish it (`a tier of the standing residency could not be
started`); that word is part of the sentence rather than a field, and is never attached as one.

**Two things never appear in a rendered line**, and the formatter removes them rather than each
call site. A
field whose name looks like a secret (`token`, `password`, `secret`, `credential`, `api_key`,
`authorization`, `cookie`, and anything containing one of those) prints `<redacted>` in place of
its value, the key still there so a withheld field reads differently from a missing one. The same
names are withheld inside a structured field too, so a tool call's `arguments` prints
`{"password":"<redacted>"}` for a key the model named `password`, and a structure nested too deep
to read through prints `<redacted>` whole. And the
credential inside any URL is stripped from the whole line, message and traceback included, so a
`redis://` or `imap://` connection error names its host and never its password.

For a deployment that collects lines rather than reading them, `CORTEX_LOG_FORMAT=packed` writes
one JSON object per line instead, with the fields under their own `fields` key:

```sh
CORTEX_LOG_FORMAT=packed docker compose up -d --build
docker compose logs brain | sed 's/^brain-1  | //' | jq -c 'select(.fields.model)'
```

The sidecar has its own half of the same knob, `CORTEX_MODELHOST_LOG_FORMAT`, under its own
container's prefix. A name neither build carries fails the process at startup rather than falling
back to a rendering nobody asked for, so a typo is loud.

The two per-line trails worth knowing about are the tool audit (`cortex.tools.audit`, always on,
[tools-mcp.md](tools-mcp.md)) and the recall trail (`cortex.memory.recall`, behind
`CORTEX_MEMORY_RECALL_AUDIT`, [memory-pgvector.md](memory-pgvector.md)). Both write a bare message
and put everything in fields, so they are read the way every other line here is.

A reply the output guardrail removed a link from logs one line when it settles, with a count per
ground and the policy set by `CORTEX_OUTPUT_GUARDRAIL`, and never the link or its host:

```text
INFO:cortex_core.turn_output:the output guardrail removed links from this reply collected=<links taken from untrusted results> link=<links taken on a strict or image turn> lookalike=<links only a non-ASCII host took> policy=<redact, lookalike or strict>
```

Each link is counted once, under the first ground that took it, so under `policy=lookalike` the
sum of `lookalike=` over a week is how many links that policy removed beyond the default's. A
reply that lost nothing logs nothing.

## Talk Converse from the host

With a brain running either way, one full turn over the real seam (the deterministic
echo backend answers on the default path; real inference is the opt-in GPU override,
`CORTEX_INFERENCE_BACKEND=llamacpp` from Slice 4, [llamacpp-gpu.md](llamacpp-gpu.md)):

```sh
cd brain && uv run python - <<'EOF'
import asyncio
from grpc import aio
import cortex_seam as seam

async def turn(session_id: str, text: str) -> None:
    async with aio.insecure_channel("127.0.0.1:50051") as channel:
        stub = seam.BrainServiceStub(channel)
        call = stub.Converse()
        await call.write(seam.ClientEvent(session_id=session_id, user_turn=seam.UserTurn(text=text)))
        await call.done_writing()
        parts = []
        async for event in call:
            kind = event.WhichOneof("event")
            if kind == "text_delta":
                parts.append(event.text_delta.text)
            elif kind == "turn_complete":
                print("turn_id:", event.turn_complete.turn_id)
        print("reply:", "".join(parts))

asyncio.run(turn("dev-session", "hello"))
EOF
```

Expected on a fresh session: `reply: reply 1: hello`. Re-run with a different text and
the counter increments; `docker compose restart brain` in between must NOT reset it
(see the Redis section above). Full stream semantics (Cancel, SeamError codes):
[modules/brain-orchestrator.md](../modules/brain-orchestrator.md).

## The live seam check (body → brain)

With a brain running either way, run the Rust integration suite. It is `#[ignore]`d, never
in CI, never under coverage (ADR-0003 d3; details in
[modules/body-rpc.md](../modules/body-rpc.md)):

```sh
CORTEX_SEAM_TOKEN=<value> just up          # or just brain-serve
CORTEX_SEAM_TOKEN=<value> just seam-health
```

**The token is a precondition of the suite, not an option** (ADR-0016 addendum on the
checked precondition). One check proves a wrong token is refused, and a brain serving
without one accepts every token there is, so that check fails on a stack that is merely
unconfigured. `just seam-health` stops with an error when the variable is unset and prints what to
do; a token written into `.env` reaches compose, which reads that file, and not `just`,
which does not. To check a token-free brain anyway, run the suite by hand with that one
check skipped, and say so in what you report:

```sh
cd body && cargo test -p body-rpc --test live -- --ignored --skip a_rejected_seam_token
```

Set `CORTEX_BRAIN_ADDR` first if the brain is not on defaults. One check in the suite needs
no brain at all: it dials a loopback peer of its own to count what the connection indicator's
probe spends, since a dial to a closed port is refused on some hosts and silently dropped on
this one (ADR-0024 host-shape addendum). A quick Python-side probe of the same RPC (it is
what the container healthcheck runs):

```sh
cd brain && uv run python -c "import grpc, cortex_seam as seam; print(seam.BrainServiceStub(grpc.insecure_channel('127.0.0.1:50051')).Health(seam.HealthRequest(), timeout=5))"
```

The live-Redis contract suites (integration-marked, excluded from CI/coverage) run the
`SessionStore`, `HandoffStore`, and `ScheduleStore` contracts against a real server. Pass
`--no-cov` because the workspace's 100% coverage gate is meaningless for (and would fail) an
integration-only selection:

```sh
docker compose up -d redis
cd brain && uv run pytest -m integration --no-cov packages/session
```

They reach the same server `CORTEX_REDIS_URL` names but **select database 15**, which the brain
never opens, and they empty it before the suite and after every check. So the run is safe on a
machine carrying real state, it needs no cleanup of yours, and each check gets the empty store
the fakeredis fixture gives it (`brain/packages/session/tests/live_redis.py`, decided in the
[ADR-0002](../adr/ADR-0002-toolchain-checks.md) addendum on the live-run database). Two things
follow for you. Do not point `CORTEX_REDIS_URL` at database 15; the run fails at startup if you
do, rather than emptying the brain's state. And if you want to inspect what a run left behind,
look in database 15 (`redis-cli -n 15`) while it is paused, since the next `reset` clears it.

## Regenerating seam stubs

Only after editing [proto/body.proto](../../proto/body.proto) (extend, never renumber, because
v0 field numbers are frozen): run `just proto`, review the `_generated` diffs, commit
them with the proto change. Mechanics per side:
[modules/brain-seam.md](../modules/brain-seam.md) and
[modules/body-rpc.md](../modules/body-rpc.md).
