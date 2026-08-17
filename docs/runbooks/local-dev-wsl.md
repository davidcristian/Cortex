# Runbook for local development on WSL

The daily loop for working on Cortex from a WSL2 distro. Rules live in
[AGENTS.md](../../AGENTS.md); gate mechanics in
[ADR-0002](../adr/ADR-0002-toolchain-gates.md); seam codegen, packaging, and the seam
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
  [ADR-0002](../adr/ADR-0002-toolchain-gates.md) toolchain-print addendum), so this machine and CI
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
  writer, which the gate refuses on purpose (ADR-0002 single-verdict addendum).
- **just** provides `just check`, THE gate (AGENTS.md gate 6); run it before calling
  anything done.
- **Every suite in that gate runs shuffled under a fixed seed** (the
  [ADR-0002](../adr/ADR-0002-toolchain-gates.md) shuffle addendum): `--randomly-seed=9973` in
  `brain/pyproject.toml`, `7919` in `scripts/pyproject.toml`, `sequence: { shuffle: true, seed:
  65537 }` in `body/app/vite.config.ts`. So the order is not the collection order and is still the
  same order twice; a red run reproduces exactly, here and in CI, and pytest prints
  `Using --randomly-seed=N` in its header so the log names the order it ran in. Reproducing a
  failure needs nothing special, but reproducing it in ISOLATION does: pass the seed the header
  printed, `uv run pytest --randomly-seed=9973 <path>`, or the test will run in a different order
  than the failing run did. Do not tune a seed to make a test pass; that throws away every draw
  the suite has survived and hides the dependency rather than fixing it.
- **`just shuffle [seed]`** is the deliberate sweep, and the one thing `just check` does not do:
  all three suites at ONE seed of your choosing, a random one by default, printed so the run
  reproduces with `just shuffle <seed>`. Run it when a test behaves as though a sibling left
  something behind, and after landing a batch of tests. It is not in CI, its whole point being an
  order nobody chose.
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
cd body && cargo test -p body-rpc --test live -- --ignored
```

Set `CORTEX_BRAIN_ADDR` first if the brain is not on defaults. A quick Python-side
probe of the same RPC (it is what the container healthcheck runs):

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
[ADR-0002](../adr/ADR-0002-toolchain-gates.md) addendum on the live-run database). Two things
follow for you. Do not point `CORTEX_REDIS_URL` at database 15; the run refuses to start if you
do, rather than emptying the brain's state. And if you want to inspect what a run left behind,
look in database 15 (`redis-cli -n 15`) while it is paused, since the next `reset` clears it.

## Regenerating seam stubs

Only after editing [proto/body.proto](../../proto/body.proto) (extend, never renumber, because
v0 field numbers are frozen): run `just proto`, review the `_generated` diffs, commit
them with the proto change. Mechanics per side:
[modules/brain-seam.md](../modules/brain-seam.md) and
[modules/body-rpc.md](../modules/body-rpc.md).
