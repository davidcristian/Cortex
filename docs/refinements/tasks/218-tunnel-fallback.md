# Q3 body-initiated-stream tunnel fallback

**Status:** open, fix when it bites
**Area:** body-gateway
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)
**Trigger:** `host.docker.internal` failing, from a bridge-network container on this
host, to reach a host service bound to an interface a container can see.
**Verified:** 2026-09-11

Body gateway & OS actions in Slice 9 ([ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)): each
behind the unchanged `BodyGateway`/`AudioControl`/`BodyService` seams.

The brain dials the body directly today; if
`host.docker.internal` proves brittle on WSL2, tunneling body-directed calls over a
body-initiated bidi stream is a different `BodyGateway` adapter, with no core/tool/proto change.

## Trail

- 2026-09-06: **Not fired**, measured on this host rather than argued, and the trigger above is
  narrowed to the reach the body needs so the next reader measures the same thing. A
  `python3 -m http.server` bound to `0.0.0.0:50251` on the WSL host was dialled from an `alpine`
  container on the default bridge, started with `--add-host host.docker.internal:host-gateway`:
  the name resolves to Docker Desktop's own gateway, `192.168.65.254` and `fdc4:f303:9324::254`,
  and the round-trip succeeds. The host's real LAN address on the mirrored `eth6`, `192.168.0.64`,
  times out from the same container in the same run, so on this machine it is the LAN address that
  does not carry and the automatic name that does. Check the listener with `ss -ltn` before
  believing a refusal: a first reading here said refused because the measurement's own server had
  exited.
- 2026-09-06: The refusal recorded against the ProtonMail Bridge is a different fact and does not
  fire this trigger. The Bridge binds `127.0.0.1` only, which no name reaches from a container,
  and `docker/docker-compose.body.yml` already instructs the operator to bind the body to
  `0.0.0.0:50151` for exactly that reason. A service that binds loopback is unreachable by the
  container whatever the endpoint resolves to, so it says nothing about the endpoint.
- 2026-09-11: measured again on this host and still not fired. Port 50251 is held on the
  Windows side today, so the bind in WSL failed with `EADDRINUSE` while `ss -ltn` listed no
  listener; the probe moved to a kernel-chosen port, 46033, and the listener was confirmed with
  `ss -ltn` before any dial. From `alpine:latest` on the default bridge, both with
  `--add-host host.docker.internal:host-gateway` and without it, the name resolved to
  `192.168.65.254` (the add-host run also listed `fdc4:f303:9324::254`) and the GET landed, two
  lines in the server's log, both seen from `127.0.0.1`. The LAN address, `192.168.0.64` on
  `eth5` today, produced no request at the server within an 8 s timeout, as on 2026-09-06.
  `docker/docker-compose.body.yml` still instructs the operator to bind the body to
  `0.0.0.0:50151` (lines 11-12) and still adds the `host-gateway` alias (line 55).
