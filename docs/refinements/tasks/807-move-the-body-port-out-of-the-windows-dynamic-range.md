# Move the body's port out of the Windows dynamic port range

**Status:** open, waiting for its trigger
**Area:** body-gateway
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md) decision 6
**Trigger:** the host's excluded TCP port ranges, from `netsh interface ipv4 show excludedportrange
protocol=tcp`, written in this file's History, or a Windows body printing `could not bind
BodyService` on its default port.
**Verified:** 2026-10-07

The body serves `BodyService` on `CORTEX_BODY_ADDR`, default `127.0.0.1:50151`
(`DEFAULT_BODY_PORT` in `body/app/src-tauri/src/body_server.rs`), and the brain's
`CORTEX_BODY_ENDPOINT` defaults to `host.docker.internal:50151` in `docker/docker-compose.body.yml`.
Port 50151 lies in Windows' dynamic port range, 49152 to 65535, where Hyper-V, WSL and Docker
reserve blocks of ports at boot that no other process may bind.

On the development machine, under WSL's mirrored networking, the Linux shell could not bind it:
50151, 50161 and 50171 failed with `Address already in use` while nothing in WSL listened on them,
and 40151, 49151 and 51151 bound. 23 shell logs from 2026-10-06 hold `cortex: could not bind
BodyService on 127.0.0.1:50151`; those runs went on without a body server, which nothing else
reported, because none of them needed one.
The [capture turns](../../readings/capture-turns.md) ran on 40151 instead. The cause is assumed, not
read: interop is off in that WSL distribution, so `netsh` could not be run to list the reserved
blocks.

If the host reserves 50151 too, the Windows shell starts, prints the line and serves no capture,
volume or toast, and the brain's calls fail as unreachable. The brain's own 50051 sits in the same
range.

## What to do

Read the host's reserved ranges. If either port is in one, move both defaults below 49152 in the
shell, the compose files, the tests and the docs that name them, and decide in ADR-0023 whether a
failed bind should stop the shell rather than leave it running without a body server.

## History

- 2026-10-07: filed from the capture turns of the display capture host check
  ([H-012](../../host/tasks/012-display-capture-path.md)).
