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
  `127.0.0.1` are reachable from both WSL and Windows. No GPU wiring exists yet. The
  `docker-compose.gpu.yml` override arrives with Slice 4 (docs/ROADMAP.md).
  Footgun: `docker-credential-desktop.exe … exec format error` means the shell lacks
  WSL interop (Docker Desktop's credential helper is a Windows binary); run from a
  shell with interop, or point `DOCKER_CONFIG` at a config without a `credsStore`.

## Seam configuration (env only)

| Variable | Default | Read by |
|---|---|---|
| `CORTEX_SEAM_HOST` | `127.0.0.1` | brain server bind host (Compose sets `0.0.0.0` inside the container; exposure stays loopback-only via the port publish) |
| `CORTEX_SEAM_PORT` | `50051` | brain server bind port |
| `CORTEX_BRAIN_ADDR` | `http://127.0.0.1:50051` | body-side live check (the address it dials) |

The defaults line up: a brain on defaults is reachable by a body check on defaults.
Everything listens on loopback only (ROADMAP assumption 5).

## Run the brain

Natively, for fast iteration (uv syncs automatically):

```sh
cd brain && uv run python -m cortex_orchestrator
```

In Compose, the deployed shape (from the repo root):

```sh
docker compose up -d --build
docker compose ps            # wait for "healthy" (the healthcheck calls the real Health RPC)
docker compose logs -f brain
docker compose down
```

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

## Regenerating seam stubs

Only after editing [proto/body.proto](../../proto/body.proto) (extend, never renumber, because
v0 field numbers are frozen): run `just proto`, review the `_generated` diffs, commit
them with the proto change. Mechanics per side:
[modules/brain-seam.md](../modules/brain-seam.md) and
[modules/body-rpc.md](../modules/body-rpc.md).
