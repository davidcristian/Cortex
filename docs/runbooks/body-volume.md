# Runbook for Slice 9 host half: the brain→body volume seam

Slice 9 (ADR-0023) opens the **brain→body** direction of the seam: the dockerized brain becomes
a gRPC client of the host body's `BodyService`, and the cortex gets `get_volume`/`set_volume`
built-in tools. The CI-gated half (both sides, fakes) is green under `just check`. This runbook
covers the two host halves, both the agent-runnable brain→body dial across the container boundary,
and the host-only Windows validation with real Core Audio.

## What crosses the seam

- The brain reads `CORTEX_BODY_BACKEND=grpc` + `CORTEX_BODY_ENDPOINT` (default
  `host.docker.internal:50151`) and builds a `GrpcBodyGateway` (`cortex_body_client`).
- The body binds `CORTEX_BODY_ADDR` (default `127.0.0.1:50151`) and serves
  `body_rpc::body_service(WindowsAudioControl::new(), WindowsNotify::new(&app_id), &token)`, the
  `BodyService` server fronted by the `SeamTokenValidator`. Each handler runs its synchronous OS
  call on a blocking thread, so a slow endpoint never parks the runtime.
- The seam token is the **same** shared `CORTEX_SEAM_TOKEN` as the `BrainService` direction: the
  brain client attaches `x-cortex-seam-token`, the body server checks it (ADR-0016, mirrored).
  Empty disables auth both ways.

## Connectivity (assumption 3 / assumption 5)

The container reaches the host via `host.docker.internal`; `docker/docker-compose.body.yml` adds
the `host-gateway` `extra_hosts` entry the portable path needs. **Loopback is not enough for the
container→host path:** the container cannot reach the host's `127.0.0.1`, so for the real dial
the body must bind an interface the container can see. Set `CORTEX_BODY_ADDR=0.0.0.0:50151` on
the host and let the host firewall keep the port host-local. Once the bind is not pure loopback,
the **seam token is the boundary**. Set `CORTEX_SEAM_TOKEN` on both sides (ADR-0023 revisits
assumption 5 here). The `BodyGateway`/`AudioControl` ports stay abstract so the ADR-0001 Q3
fallback (a body-initiated tunnel) would be a pure adapter swap, no seam change.

## Agent half (the brain→body dial across the container boundary)

Proves the reversed seam token, the wire, and the round-trip without needing real audio. Stand
up **any** `BodyService` server on the host and point the brain's live test at it:

- Against the **real** Windows body (user path): run the Tauri app (below), then from the brain
  image (or a host venv):
  ```
  cd brain && CORTEX_BODY_ENDPOINT=host.docker.internal:50151 CORTEX_SEAM_TOKEN=... \
  uv run pytest -m integration --no-cov packages/body_client
  ```
- Against a host-side test server (no Windows, no real audio): serve a canned
  `BodyServiceServicer` on the host (the fake in `packages/body_client/tests/test_gateway.py` is
  the template), bind it where the container can reach it, and run the same live test with
  `CORTEX_BODY_ENDPOINT` set to it. The live test reads the volume, nudges it, and restores it,
  so it leaves the host as it found it.

Note: on an 8 GB GPU the gemma-4-12B cortex does not fit, so a fully *cortex-driven*
`set_volume` (the model emitting the tool call) is bounded by what fits; the seam + gateway +
tool path are what this half validates directly.

**Validated 2026-07-08 (agent, [ADR-0023 addendum](../adr/ADR-0023-body-gateway-volume.md)):**
the host-side-test-server path, run end to end. A token-requiring fake `BodyService` served on
`0.0.0.0:50151` from the brain venv; `test_gateway_live.py` ran from a container (the uv builder
image with the brain workspace mounted (the runtime image has no dev deps) plus
`--add-host host.docker.internal:host-gateway`): the tokened round-trip **passed** and the same
run without `CORTEX_SEAM_TOKEN` was rejected `UNAUTHENTICATED: invalid or missing seam token`.

## Host-only half (real Core Audio on Windows)

What this closes and where to record it: [docs/host/windows-desktop.md](../host/windows-desktop.md).

`WindowsAudioControl` (`os_windows`, Core Audio via the `windows` crate, ADR-0023-scoped
`unsafe`) is `cfg(windows)` and never built or measured in CI. Validate it on Windows:

1. Bring up the brain with the body override and a token:
   ```
   set CORTEX_SEAM_TOKEN=<shared-secret>
   docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.body.yml up -d --build
   ```
   (add `-f docker/docker-compose.gpu.yml` for the real cortex if the GPU fits it).
2. Build + run the body, binding an interface the container can reach and allowing the port
   through the Windows firewall (host-local):
   ```
   set CORTEX_BODY_ADDR=0.0.0.0:50151
   set CORTEX_SEAM_TOKEN=<shared-secret>
   cd body/app && npm run tauri dev
   ```
3. Summon the overlay (the hotkey) and say/type **"set volume to 30%"**. The cortex emits
   `set_volume`, the audited dispatcher runs it (ungated, so no confirm card), the brain dials the
   body over `host.docker.internal`, and the host output volume moves. "What's my volume?"
   exercises `get_volume`.

Volume is **ungated** (reversible), so no approval card appears. To require confirmation, add
`set_volume` to `CORTEX_TOOLS_GATED` (the dispatcher backstop). Then a clean turn prompts the
overlay card and a tainted turn is denied outright (ADR-0022).
