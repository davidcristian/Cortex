# Runbook: local development on WSL

The daily loop for working on Cortex from a WSL2 distro. The rules are in
[AGENTS.md](../../AGENTS.md), the check mechanics in
[ADR-0002](../adr/ADR-0002-toolchain-checks.md), and the gRPC codegen, packaging and config
contract in [ADR-0003](../adr/ADR-0003-generated-stubs.md).

## One-time setup inside the distro

- **uv** runs every Python project, the `brain/` workspace and `scripts/`.
- **rustup** with stable as the default, plus nightly for branch coverage only:
  `rustup toolchain install nightly --component llvm-tools-preview`.
- **The `x86_64-pc-windows-msvc` target** on stable, so `check-body` can clippy the
  `cfg(windows)` `os_windows` backend that compiles to nothing natively:
  `rustup target add x86_64-pc-windows-msvc`. Clippy never links, so no MSVC toolchain is needed.
- **cargo-llvm-cov**, via `cargo install cargo-llvm-cov`.
- **just**, which provides `just check`, the one command that must pass before anything is
  called done.
- **pre-commit**, installed once with `pre-commit install`; the hook is a literal `just check`.
- **protoc 35.x**, needed only to regenerate the committed gRPC stubs with `just proto`. Normal
  builds and CI never run it.
- **Docker Desktop on Windows** with WSL integration enabled for this distro (Settings,
  Resources, WSL integration). The daemon runs on Windows, the `docker` and `docker compose` CLIs
  inside WSL talk to it, and ports published on `127.0.0.1` are reachable from both WSL and
  Windows. The base compose file is GPU-free; real inference is the opt-in
  `docker/docker-compose.gpu.yml` override ([llamacpp-gpu.md](llamacpp-gpu.md)). A
  `docker-credential-desktop.exe … exec format error` means the shell lacks WSL interop, since
  Docker Desktop's credential helper is a Windows binary; run from a shell with interop, or point
  `DOCKER_CONFIG` at a config with no `credsStore`.

Neither nightly nor cargo-llvm-cov is fixed to a version, by decision, so this machine and CI
routinely resolve different ones. `check-body` prints `rustc +nightly --version` and `cargo
+nightly llvm-cov --version` before it measures and hands both to the check, which repeats them
next to the numbers they produced:

```
measured by cargo-llvm-cov 0.8.7, llvm export 3.1.0
measured by rustc 1.98.0-nightly (4c9d2bfe4 2026-07-01)
PASS lines: 100.00%
```

When the coverage check fails, read those lines against the ones in a CI log first: a toolchain
that moved and a commit that broke coverage look identical in the totals and nowhere else. Two
failures are about the report rather than the code. `FAIL producer:` means the `body/coverage.json`
being judged was written by a different cargo-llvm-cov than the one that just ran. `coverage report
has no 'cargo_llvm_cov' entry` means the export stopped naming its writer, which counts as a
failure by design.

## Test order

Every suite runs shuffled under a fixed seed. How to reproduce a failure at that order, and what
`just shuffle` adds: [test-order.md](test-order.md).

## Configuration, which is environment variables only

| Variable | Default | Read by |
|---|---|---|
| `CORTEX_SEAM_HOST` | `127.0.0.1` | brain server bind host (Compose sets `0.0.0.0` inside the container; exposure stays loopback-only via the port publish) |
| `CORTEX_SEAM_PORT` | `50051` | brain server bind port |
| `CORTEX_SEAM_TOKEN` | *(empty, auth off)* | both directions: the brain server rejects untokened body-to-brain calls when set (Compose passes it through from the host env or `.env`), the body server validates the same token on brain-to-body calls, the brain client attaches it when dialing the body, and the body live checks present the same value |
| `CORTEX_REDIS_URL` | `redis://127.0.0.1:6379/0` | brain composition root, where session state lives (Compose sets `redis://redis:6379/0`) |
| `CORTEX_MODEL_CORTEX` | `cortex` | brain composition root: the logical cortex model id, never a path |
| `CORTEX_BRAIN_ADDR` | `http://127.0.0.1:50051` | body-side live check, the address it dials |
| `CORTEX_BODY_BACKEND` | `none` | brain composition root, for the brain-to-body direction: `none` (off) or `grpc` (dial the host body, wiring the `get_volume` and `set_volume` tools) |
| `CORTEX_BODY_ENDPOINT` | *(required when `grpc`)* | brain composition root: the host body the brain dials, `host.docker.internal:50151` from the dockerized brain |
| `CORTEX_BODY_ADDR` | `127.0.0.1:50151` | body server bind address; set `0.0.0.0:50151` for the real container-to-host path, where the token and the host firewall are then the boundary |

The defaults line up: a brain on defaults is reachable by a body check on defaults and finds a
redis published by Compose on loopback. Everything listens on loopback only. The brain-to-body
direction has its own end-to-end procedure in [body-volume.md](body-volume.md).

### How the composed brain receives a setting

The brain container gets only the variables its compose files name, so a setting exported in the
shell or written in the repo-root `.env` reaches it only when some layered file names that
variable. Each of the brain's settings is named in one of three ways.

- **Passed through by name**, a bare key such as `CORTEX_OUTPUT_GUARDRAIL:`. Set on the host, the
  value reaches the brain; unset, the variable never enters the container and the settings class's
  own default applies. The base file passes the settings that apply to every stack (history
  window, output guardrail, titles, reply bounds, buffer and confirm timeout, VRAM budget, tool
  approval, costs and audit file, schedule pacing). Each override passes the ones its capability
  reads: `docker-compose.gpu.yml` the inference and handoff settings and the two logical model
  ids, `docker-compose.memory.yml` the recall settings, `docker-compose.subagents.yml` the
  delegation bounds.
- **Passed with a compose default**, `${CORTEX_X:-value}`, where the default is written in the
  compose file as well as in Python (`CORTEX_SEAM_TOKEN`, `CORTEX_LOG_FORMAT`, the tool salience
  settings and call timeout, the schedule backend and zone, the body settings, the subagent
  resource figures). `scripts/crosscheck.py` compares the body and subagent figures against their
  Python declarations; the others are not compared, which is why a new setting is passed bare.
- **Set by the file**, where the topology decides the value: `CORTEX_SEAM_HOST`,
  `CORTEX_REDIS_URL`, each override's backend switch and in-network endpoints, and the memory DSN.
  Setting one of these on the host has no effect.

Two settings are named by no file, on purpose. `CORTEX_SEAM_PORT` is fixed at 50051 by the base
file's publish and its healthcheck, and `CORTEX_TOOLS_ENDPOINT` is the single-sidecar form that
the tool overrides replace with one `CORTEX_TOOLS_ENDPOINTS__<name>` key each; the brain refuses
both at once. The map-shaped settings `CORTEX_TOOLS_ALLOW` and `CORTEX_SUBAGENTS_ROSTER` are
contributed one key at a time by the override that brings the server they describe.
`just check-settingscheck` fails when a settings field reaches its service from no file and is not
one of those two, and it treats the model host and the email sidecar the same way. To see what a
given stack will hand the brain, render it without starting anything:

```bash
docker compose --project-directory . -f docker/docker-compose.yml [-f <override> ...] config brain
```

A key rendered as `null` is a pass-through whose variable is unset on the host.

## Redis, the session store

Compose runs a `redis` service (image `redis:8-alpine`) beside the brain, with `--appendonly yes`
and the named volume `redis-data`, so sessions survive a redis restart. `docker compose down -v`
is the reset switch and wipes all conversations. The port is published on `127.0.0.1` only:

```sh
docker compose exec redis redis-cli keys 'cortex:session:*'
docker compose exec redis redis-cli lrange 'cortex:session:<session-id>:messages' 0 -1
```

That is one JSON document per message (`{"role", "text", "at", "turn_id"}`), whose layout is in
[modules/brain-session.md](../modules/brain-session.md).

**State survives a brain restart.** Conversation state lives only in redis, so a plain
`docker compose restart brain` preserves every conversation: run a turn, restart the brain
container while redis keeps running, run another turn in the same session, and the deterministic
reply counter keeps counting (`reply 1: …`, then `reply 2: …`).

## Run the brain

Natively, for fast iteration, with uv syncing automatically. It needs a reachable redis, which the
Compose redis service provides:

```sh
docker compose up -d redis
cd brain && uv run python -m cortex_orchestrator
```

In Compose, the deployed shape, from the repo root:

```sh
docker compose up -d --build
docker compose ps            # wait for "healthy" (the brain healthcheck calls the real Health RPC)
docker compose logs -f brain
docker compose down
```

## Read the brain's logs

How a rendered line is built, what the formatter withholds and how to search one:
[brain-logs.md](brain-logs.md).

## Talk Converse from the host

With a brain running either way, one full turn over the real gRPC service. The deterministic echo
backend answers on the default path; real inference is the opt-in GPU override,
`CORTEX_INFERENCE_BACKEND=llamacpp` ([llamacpp-gpu.md](llamacpp-gpu.md)).

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

Expected on a fresh session: `reply: reply 1: hello`. Re-run with a different text and the counter
increments, and `docker compose restart brain` in between must not reset it. Full stream
semantics, Cancel and the error codes, are in
[modules/brain-orchestrator.md](../modules/brain-orchestrator.md).

## The live check from the body

With a brain running either way, run the Rust integration suite. It is `#[ignore]`d, never in CI,
never under coverage; details in [modules/body-rpc.md](../modules/body-rpc.md).

```sh
CORTEX_SEAM_TOKEN=<value> just up          # or just brain-serve
CORTEX_SEAM_TOKEN=<value> just rpc-health
```

**The token is a precondition of the suite, not an option.** One check proves a wrong token is
refused, and a brain serving without one accepts every token there is, so that check fails on a
stack that is merely unconfigured. `just rpc-health` stops with an error when the variable is
unset; a token written into `.env` reaches compose, which reads that file, and not `just`, which
does not. To check a token-free brain anyway, run the suite by hand with that one check skipped,
and say so in what you report:

```sh
cd body && cargo test -p body-rpc --test live -- --ignored --skip a_rejected_rpc_token
```

Set `CORTEX_BRAIN_ADDR` first if the brain is not on defaults. One check in the suite needs no
brain at all: it dials a loopback peer of its own to count what the connection indicator's probe
spends, since a dial to a closed port is refused on some hosts and silently dropped on this one. A
quick Python-side probe of the same RPC, which is what the container healthcheck runs:

```sh
cd brain && uv run python -c "import grpc, cortex_seam as seam; print(seam.BrainServiceStub(grpc.insecure_channel('127.0.0.1:50051')).Health(seam.HealthRequest(), timeout=5))"
```

The live-Redis contract suites are integration-marked and excluded from CI and coverage. They run
the `SessionStore`, `HandoffStore` and `ScheduleStore` contracts against a real server. Pass
`--no-cov`, because the workspace's 100% coverage threshold would fail an integration-only
selection:

```sh
docker compose up -d redis
cd brain && uv run pytest -m integration --no-cov packages/session
```

They reach the same server `CORTEX_REDIS_URL` names but select database 15, which the brain never
opens, and they empty it before the suite and after every check, so the run is safe on a machine
holding real state and needs no cleanup of yours. Do not point `CORTEX_REDIS_URL` at database 15;
the run fails at startup if you do, rather than emptying the brain's state. To inspect what a run
left behind, look in database 15 (`redis-cli -n 15`) while it is paused, since the next reset
clears it.

## Regenerating the gRPC stubs

Only after editing [proto/body.proto](../../proto/body.proto), which may be extended but never
renumbered, because v0 field numbers are fixed: run `just proto`, review the `_generated` diffs,
and commit them with the proto change. The mechanics per side are in
[the brain's stub package](../modules/brain-seam.md) and
[the body's rpc crate](../modules/body-rpc.md).
