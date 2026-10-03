# Tunnelling body-directed calls over a body-initiated stream

**Status:** open, waiting for its trigger
**Area:** body-gateway
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)
**Trigger:** a GET from `alpine:latest` on the default bridge network to
`host.docker.internal:<port>` failing while a `python3 -m http.server` bound to `0.0.0.0` on this
host listens on that port, which `ss -ltn` confirms before the dial. The same reach to the
Windows-side body is observed by host task 002, not here.
**Verified:** 2026-10-03

The brain dials the body directly, at `CORTEX_BODY_ENDPOINT` through `GrpcBodyGateway.connect`. If
`host.docker.internal` proves unreliable on WSL2, tunnelling body-directed calls over a
body-initiated bidirectional stream needs four things and no core or tool change: one new streaming
RPC on `BrainService` in `proto/body.proto`, since that stream crosses the boundary and every call
that crosses it is declared there; a body-side loop that opens it and serves the `BodyService`
calls that arrive on it; a different `BodyGateway` adapter in the brain; and the composition root's
part, a `BrainService` handler that hands the stream to that adapter and a third value in
`BodyBackendName` (`cortex_orchestrator/config_body.py`, today `none` and `grpc`) that
`build_body_gateway` in `builders.py` selects it by.


## History

- 2026-09-06: Not fired, measured on this host rather than argued, and the trigger narrowed to the
  reach the body needs. A `python3 -m http.server` bound to `0.0.0.0:50251` on the WSL host was
  dialled from an `alpine` container on the default bridge, started with
  `--add-host host.docker.internal:host-gateway`: the name resolves to Docker Desktop's own gateway,
  `192.168.65.254` and `fdc4:f303:9324::254`, and the round trip succeeds. The host's real LAN
  address on the mirrored `eth6`, `192.168.0.64`, times out from the same container in the same run.
  Check the listener with `ss -ltn` before believing a refusal: a first reading here said refused
  because the measurement's own server had exited.
- 2026-09-06: The refusal recorded against the ProtonMail Bridge is a different fact and does not
  fire this trigger. The Bridge binds `127.0.0.1` only, which no name reaches from a container, and
  `docker/docker-compose.body.yml` already tells the operator to bind the body to `0.0.0.0:50151`
  for exactly that reason.
- 2026-09-11: Measured again and still not fired. Port 50251 is held on the Windows side today, so
  the bind in WSL failed with `EADDRINUSE`; the probe moved to a kernel-chosen port, 46033,
  confirmed with `ss -ltn` before any dial. From `alpine:latest` on the default bridge, with and
  without the `host-gateway` alias, the name resolved to `192.168.65.254` and the GET succeeded. The
  LAN address, `192.168.0.64` on `eth5` today, produced no request within an 8 s timeout.
- 2026-09-17: Measured again and still not fired. A `python3 -m http.server` on `0.0.0.0` at the
  kernel-chosen port 43778, confirmed with `ss -ltn` first, was dialled from `alpine:latest` on the
  default bridge: with the alias the name resolved to `fdc4:f303:9324::254` and without it to
  `192.168.65.254`, and both GETs succeeded. The LAN address, `192.168.0.196` on `eth0` today, timed
  out after 8 s. No commit since 2026-09-11 touches `docker/docker-compose.body.yml` or
  `docker/docker-compose.yml`.
- 2026-09-24: Checked against the tree and not measured again, because Docker was held by a
  running measurement session, so the 2026-09-17 reading is the latest. No commit since then
  touches the `host.docker.internal` lines in `docker/docker-compose.body.yml`. The entry said the
  tunnel was an adapter with no proto change; it needs a new streaming RPC and a body-side loop too.
- 2026-10-03: Measured again and not fired, beside a running measurement container, with a dial
  that used no GPU and published no port. A `python3 -m http.server` on `0.0.0.0`
  at the kernel-chosen port 43772, confirmed with `ss -ltnp` first, was dialled from
  `alpine:latest` on the default bridge under Docker Desktop 4.92.0 (engine 29.8.0): with the
  `host-gateway` alias the name resolved to `fdc4:f303:9324::254` and without it to
  `192.168.65.254`, and both GETs succeeded. The LAN address, `192.168.0.33` on `eth1` today, timed
  out after 8 s. The listener is on the WSL side; the dial to the Windows-side body is host task
  002's. Two corrections: the trigger now names the command that decides it, and the tunnel also
  needs the composition root's selection and stream handler, which the entry had not counted.
