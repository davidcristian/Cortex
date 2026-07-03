# Runbook for local development on WSL

The daily loop for working on Cortex from a WSL2 distro. Rules live in
[AGENTS.md](../../AGENTS.md); gate mechanics in
[ADR-0002](../adr/ADR-0002-toolchain-gates.md); seam codegen, packaging, and the seam
config contract in [ADR-0003](../adr/ADR-0003-seam-codegen.md).

## Prerequisites (one-time, inside the distro)

- **uv** runs every Python project (the `brain/` workspace and `scripts/`).
- **rustup** with **stable** (default) plus **nightly** for branch coverage only
  (ADR-0002 d1): `rustup toolchain install nightly --component llvm-tools-preview`.
- **cargo-llvm-cov** installs via `cargo install cargo-llvm-cov`.
- **just** provides `just check`, THE gate (AGENTS.md gate 6); run it before calling
  anything done.
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
| `CORTEX_SEAM_TOKEN` | *(empty, auth off)* | both sides (ADR-0016): the brain rejects untokened calls when set (Compose passes it through from the host env/`.env`); the body/live checks present the same value |
| `CORTEX_REDIS_URL` | `redis://127.0.0.1:6379/0` | brain composition root (where session state lives; Compose sets `redis://redis:6379/0`) |
| `CORTEX_MODEL_CORTEX` | `cortex` | brain composition root (the LOGICAL cortex model id (ADR-0004), never a path) |
| `CORTEX_BRAIN_ADDR` | `http://127.0.0.1:50051` | body-side live check (the address it dials) |

The defaults line up: a brain on defaults is reachable by a body check on defaults and
finds a redis published by Compose on loopback. Everything listens on loopback only
(ROADMAP assumption 5).

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

The live-Redis contract suite (integration-marked, excluded from CI/coverage) runs
against `CORTEX_REDIS_URL`. Pass `--no-cov` because the workspace's 100% coverage
gate is meaningless for (and would fail) an integration-only selection:

```sh
docker compose up -d redis
cd brain && uv run pytest -m integration --no-cov packages/session
```

## Regenerating seam stubs

Only after editing [proto/body.proto](../../proto/body.proto) (extend, never renumber, because
v0 field numbers are frozen): run `just proto`, review the `_generated` diffs, commit
them with the proto change. Mechanics per side:
[modules/brain-seam.md](../modules/brain-seam.md) and
[modules/body-rpc.md](../modules/body-rpc.md).
