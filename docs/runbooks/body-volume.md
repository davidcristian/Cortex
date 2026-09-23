# Runbook: the brain-to-body direction, and system volume

The dockerized brain is a gRPC client of the host body's `BodyService`, and the cortex gets
`get_volume` and `set_volume` built-in tools ([ADR-0023](../adr/ADR-0023-body-gateway-volume.md)).
CI covers both sides against fakes. This runbook covers the two halves it cannot: the dial from
the container to the host, which the agent can run, and the Windows check with real Core Audio,
which only the host can run.

## What crosses

The brain reads `CORTEX_BODY_BACKEND=grpc` and `CORTEX_BODY_ENDPOINT` (default
`host.docker.internal:50151`) and builds a `GrpcBodyGateway` from `cortex_body_client`. The body
binds `CORTEX_BODY_ADDR` (default `127.0.0.1:50151`) and serves
`body_rpc::body_service(WindowsAudioControl::new(), WindowsNotify::new(&app_id), &token)`, the
`BodyService` server behind the `SeamTokenValidator`. Each handler runs its synchronous OS call on
a blocking thread, so a slow endpoint never parks the runtime.

**Every call is bounded**, by `CORTEX_BODY_CALL_TIMEOUT_S` (default `5.0`) for volume and notify
and `CORTEX_BODY_CAPTURE_TIMEOUT_S` (default `10.0`) for a capture. That blocking thread is what
makes the short bound necessary: Core Audio is COM, a COM call parks its thread for as long as the
audio stack takes, and nothing above the gateway bounds a tool call, so a wedged endpoint used to
hang the turn with no way out but closing the overlay. What an operator sees when one expires is
the ordinary "could not reach the body" tool result, since a deadline this side chose is the
absence of an answer. Raise the setting if a real host is slower than the default; the failure is
typed and never silent.

The token is the same shared `CORTEX_SEAM_TOKEN` as the other direction: the brain client attaches
`x-cortex-seam-token` and the body server checks it. Empty disables authentication both ways.

## Connectivity

The container reaches the host through `host.docker.internal`, and
`docker/docker-compose.body.yml` adds the `host-gateway` `extra_hosts` entry the portable path
needs. **Loopback is not enough for the container-to-host path**: the container cannot reach the
host's `127.0.0.1`, so for the real dial the body must bind an interface the container can see.
Set `CORTEX_BODY_ADDR=0.0.0.0:50151` on the host and let the host firewall keep the port
host-local. Once the bind is not pure loopback, the token is the boundary, so set
`CORTEX_SEAM_TOKEN` on both sides. The `BodyGateway` and `AudioControl` ports stay abstract, so a
body-initiated tunnel would be a pure adapter swap.

## The dial across the container boundary

This half proves the token, the wire and the round trip without needing real audio. Stand up any
`BodyService` server on the host and point the brain's live test at it.

Against the real Windows body, run the Tauri app as below, then from the brain image or a host
venv:

```
cd brain && CORTEX_BODY_ENDPOINT=host.docker.internal:50151 CORTEX_SEAM_TOKEN=... \
uv run pytest -m integration --no-cov packages/body_client
```

Against a host-side test server, with no Windows and no real audio, serve a canned
`BodyServiceServicer` on the host (the fake in `packages/body_client/tests/test_gateway.py` is the
template), bind it where the container can reach it, and run the same live test with
`CORTEX_BODY_ENDPOINT` pointed at it. The live test reads the volume, nudges it and restores it,
so it leaves the host as it found it.

What this checks directly is the gRPC path, the gateway and the tool path. A cortex-driven
`set_volume`, where the model emits the tool call, additionally needs a real Windows desktop,
because the audio backend is `cfg(windows)`.

Validated 2026-07-08: the host-side test server path, end to end. A token-requiring fake
`BodyService` was served on `0.0.0.0:50151` from the brain venv, and `test_gateway_live.py` ran
from a container, the uv builder image with the brain workspace mounted, since the runtime image
has no dev dependencies, plus `--add-host host.docker.internal:host-gateway`. The tokened round
trip passed, and the same run without `CORTEX_SEAM_TOKEN` was rejected with `UNAUTHENTICATED`.

## The Windows check, with real Core Audio

What this closes and where to record it:
[docs/host/index.md#windows-desktop](../host/index.md#windows-desktop).

`WindowsAudioControl` (`os_windows`, Core Audio through the `windows` crate) is `cfg(windows)` and
is never built or measured in CI.

1. Bring up the brain with the body override and a token. Add `-f docker/docker-compose.gpu.yml`
   for the real cortex if the card fits it.
   ```
   set CORTEX_SEAM_TOKEN=<shared-secret>
   docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.body.yml up -d --build
   ```
2. Build and run the body, binding an interface the container can reach and allowing the port
   through the Windows firewall, host-local:
   ```
   set CORTEX_BODY_ADDR=0.0.0.0:50151
   set CORTEX_SEAM_TOKEN=<shared-secret>
   cd body/app && npm run tauri dev
   ```
3. Summon the overlay with the hotkey and say or type **"set volume to 30%"**. The cortex emits
   `set_volume`, the audited dispatcher runs it, with no approval card because volume is
   reversible, the brain dials the body over `host.docker.internal`, and the host output volume
   moves. "What's my volume?" uses `get_volume`.

To require confirmation anyway, add `set_volume` to `CORTEX_TOOLS_GATED`. A clean turn then
prompts the overlay card and a tainted turn is denied outright.
